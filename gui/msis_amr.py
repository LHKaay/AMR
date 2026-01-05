import os
import threading
import time
import sqlite3
import json
import math
import uuid
import numpy as np
from .rest_api import Robot
from .gui_map_utils import parse_grid_and_meta, generate_map_base64

def calculate_bezier_path(control_points, num_points=20):
    if len(control_points) < 2: return control_points
    path = []
    if len(control_points) == 3:
        p0, p1, p2 = control_points
        for t in np.linspace(0, 1, num_points):
            x = (1-t)**2 * p0['x'] + 2*(1-t)*t * p1['x'] + t**2 * p2['x']
            y = (1-t)**2 * p0['y'] + 2*(1-t)*t * p1['y'] + t**2 * p2['y']
            path.append({'x': x, 'y': y})
    else:
        for i in range(len(control_points)-1):
            p_start, p_end = control_points[i], control_points[i+1]
            dist = math.hypot(p_end['x'] - p_start['x'], p_end['y'] - p_start['y'])
            steps = max(1, int(dist / 0.1))
            for t in np.linspace(0, 1, steps):
                path.append({'x': p_start['x'] + (p_end['x']-p_start['x'])*t, 'y': p_start['y'] + (p_end['y']-p_start['y'])*t})
        path.append(control_points[-1])
    return path

def is_point_in_area(px, py, area):
    sx, sy = area['start']['x'], area['start']['y']
    ex, ey = area['end']['x'], area['end']['y']
    hw = area['half_width']
    dx, dy = ex - sx, ey - sy
    len_sq = dx*dx + dy*dy
    if len_sq == 0: return False
    dpx, dpy = px - sx, py - sy
    dot = dpx * dx + dpy * dy
    if not (0 <= dot <= len_sq): return False
    cross = dpx * dy - dpy * dx
    return (cross * cross) <= (hw * hw * len_sq)

def dist_point_to_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0: return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

class AMRManager:
    def __init__(self):
        self.robots = {}; self.trajectories = {}
        self.last_map_hash = {}; self.cached_map_url = {}; self.last_map_update_time = {}
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_file = os.path.join(root_dir, "robot.db")
        self._init_db(); self.load_db()

    def _init_db(self):
        try: sqlite3.connect(self.db_file).execute('CREATE TABLE IF NOT EXISTS robots (name TEXT PRIMARY KEY, ip TEXT NOT NULL)').close()
        except: pass
    def load_db(self):
        if not os.path.exists(self.db_file): return
        try:
            conn = sqlite3.connect(self.db_file); cur = conn.cursor()
            for r in cur.execute("SELECT name, ip FROM robots").fetchall(): self.add_robot(r[0], r[1], False)
            conn.close()
        except: pass
    def _save_to_db(self, n, i): 
        try: c=sqlite3.connect(self.db_file); c.execute("INSERT OR REPLACE INTO robots VALUES (?,?)", (n,i)); c.commit(); c.close()
        except: pass
    def _delete_from_db(self, n):
        try: c=sqlite3.connect(self.db_file); c.execute("DELETE FROM robots WHERE name=?", (n,)); c.commit(); c.close()
        except: pass

    def add_robot(self, name, ip, db_sync=True):
        if name in self.robots: self.robots[name].disconnect()
        self.robots[name] = Robot(name, ip)
        if db_sync: self._save_to_db(name, ip)
        return self.get_robot_names()
    def delete_robot(self, n):
        if n in self.robots: self.robots[n].disconnect(); del self.robots[n]; self._delete_from_db(n)
        return list(self.robots.keys())
    def get_robot(self, name): return self.robots.get(name)
    def get_all_robots(self): return self.robots
    def get_robot_names(self): return list(self.robots.keys())

    # --- Health & System ---
    def get_robot_health_status(self, n):
        r = self.get_robot(n)
        if not r: return {"hasError": False, "errors": []}
        h = r.get_robot_health()
        if not h: return {"hasError": False, "errors": []}
        return {"hasError": h.get("hasError", False), "errors": h.get("baseError", [])}
    def clear_robot_error(self, n, error_code):
        r = self.get_robot(n)
        return r.clear_robot_error(error_code) if r else False
    def shutdown_robot(self, n):
        r = self.get_robot(n)
        return r.shutdown_robot() if r else (False, "No Robot")
    def set_robot_pose(self, n, x, y, yaw):
        r = self.get_robot(n)
        if not r: return False, "Robot Not Found"
        success, msg = r.set_pose(x, y, yaw)
        return success, msg

    # --- Home Docks & POI ---
    def get_home_docks(self, n):
        r = self.get_robot(n)
        return r.get_home_docks() if r else []
    def register_home_dock(self, n, name):
        r = self.get_robot(n)
        return r.register_home_dock(name) if r else (False, "No Robot")
    def delete_home_dock(self, n, dock_id):
        r = self.get_robot(n)
        return r.delete_home_dock(dock_id) if r else False
    def go_home(self, n):
        r = self.get_robot(n)
        if not r: return "Robot Not Found"
        return r.go_home(n)

    def get_pois(self, n): return r.get_pois() if (r:=self.get_robot(n)) else []
    
    # [UPDATED] Add POI with Yaw support
    def add_poi(self, n, name, poi_type, use_robot_pose=True, x=0, y=0, yaw=0):
        r = self.get_robot(n)
        if not r: return False, "Robot Not Found"
        poi_id = str(uuid.uuid4())
        metadata = {"display_name": name, "type": poi_type}
        # If using robot pose, pass None for pose to API
        pose = None 
        if not use_robot_pose:
            # If explicit pose, use passed values
            pose = {"x": x, "y": y, "z": 0, "yaw": yaw}
        
        return r.add_poi(poi_id, metadata, pose)

    # [UPDATED] Update POI with Yaw support
    def update_poi(self, n, poi_id, name, poi_type, x=None, y=None, yaw=None):
        r = self.get_robot(n)
        if not r: return False, "Robot Not Found"
        metadata = {"display_name": name, "type": poi_type}
        pose = None
        if x is not None and y is not None:
            # Yaw default to 0 if None
            pose = {"x": x, "y": y, "z": 0, "yaw": yaw if yaw is not None else 0.0}
        return r.update_poi(poi_id, metadata, pose)

    def delete_poi(self, n, poi_id): return r.delete_poi(poi_id) if (r:=self.get_robot(n)) else False
    def adjust_pois(self, n): return r.adjust_pois() if (r:=self.get_robot(n)) else False

    # --- Move ---
    def manual_move(self, n, c): r=self.get_robot(n); r.manual_move(n,c) if r else None
    def cmd_stop(self, n): r=self.get_robot(n); r.cmd_stop(n) if r else None
    def execute_single_move(self, n, x, y, yaw, m): r=self.get_robot(n); return r.move_to(x,y,yaw,m,["with_directed_virtual_track"] if m in [1,2] else []) if r else "No Robot"
    def execute_track_move(self, n, x, y, m): r=self.get_robot(n); return r.move_to(x,y,None,m,["with_directed_virtual_track"]) if r else "No Robot"

    # --- Area (Fixed Bounding Box Logic) ---
    def get_all_robot_areas(self, n):
        r = self.get_robot(n)
        if not r: return []
        all_areas = []
        types = ["forbidden_area", "elevator_area", "dangerous_area", "coverage_area", "maintenance_area", "sensor_disable_area", "restricted_area"]
        for atype in types:
            areas = r.get_rectangle_areas(atype)
            if isinstance(areas, list):
                for item in areas:
                    data = {"type": atype, "area": item['area']}
                    if 'metadata' in item: data['metadata'] = item['metadata']
                    if 'id' in item: data['id'] = item['id']
                    all_areas.append(data)
        return all_areas
    
    # [UPDATED] Create Area using Bounding Box (Left-Top / Right-Bottom logic)
    def create_robot_area(self, robot_name, area_type, p1, p2, door_type=0, advanced_params=None):
        r = self.get_robot(robot_name)
        if not r: return False, "Robot not found"
        
        # 1. Define Bounding Box
        min_x, max_x = min(p1['x'], p2['x']), max(p1['x'], p2['x'])
        min_y, max_y = min(p1['y'], p2['y']), max(p1['y'], p2['y'])
        
        # 2. Calculate Center and Half-Width for Axis-Aligned Rectangle
        # Slamware Area Definition: Start->End is the central axis. Half-width extends perpendicular.
        # To make a box (min_x, min_y) to (max_x, max_y):
        # Axis: (min_x, mid_y) -> (max_x, mid_y)
        # Half-width: (max_y - min_y) / 2
        
        width = max_x - min_x
        height = max_y - min_y
        
        # Avoid zero dimensions
        if width < 0.1: width = 0.1; max_x = min_x + 0.1
        if height < 0.1: height = 0.1; max_y = min_y + 0.1
        
        mid_y = (min_y + max_y) / 2
        half_width = height / 2.0
        
        metadata = {"created_by": "gradio_gui"}
        if advanced_params: metadata.update(advanced_params)

        if area_type == "forbidden_area": 
            if "escape_distance" not in metadata: metadata["escape_distance"] = "0.1"
        elif area_type == "elevator_area":
            metadata.update({"elevator_id": str(uuid.uuid4()), "elevator_sill_width": "0.5", "elevator_scheduling_point_dist": "1.0", "elevator_door_type": str(door_type)})
        elif area_type == "dangerous_area":
            if "dangerous_area_type" not in metadata: metadata["dangerous_area_type"] = "1"
            if "max_line_speed" not in metadata: metadata["max_line_speed"] = "0.5"
        elif area_type == "restricted_area":
            metadata.update({"restricted_robots_number_limit": "1", "restricted_scheduling_points": "[]"})
        elif area_type == "sensor_disable_area":
            if "sensor_type" not in metadata: metadata["sensor_type"] = "[]"
            if isinstance(metadata["sensor_type"], list):
                metadata["sensor_type"] = json.dumps(metadata["sensor_type"])

        # Construct Payload
        area_payload = {
            "start": {"x": min_x, "y": mid_y}, 
            "end": {"x": max_x, "y": mid_y}, 
            "half_width": half_width
        }
        
        return r.create_rectangle_area_direct(area_type, area_payload, metadata)
        
    def delete_robot_areas(self, n, t): r=self.get_robot(n); return r.delete_rectangle_areas(t) if r else False
    def delete_area_at_point(self, n, x, y):
        r = self.get_robot(n)
        if not r: return False, "Robot not found"
        current_all = self.get_all_robot_areas(n)
        target = next((item for item in current_all if is_point_in_area(x, y, item['area'])), None)
        if not target: return False, "No area found"
        target_type = target['type']
        same_type_areas = [a for a in current_all if a['type'] == target_type]
        r.delete_rectangle_areas(target_type)
        count = 0
        for item in same_type_areas:
            if item == target: continue
            payload = {"area": item['area'], "metadata": item.get('metadata', {"created_by": "restored"})}
            r._post(f"/api/core/artifact/v1/rectangle-areas/{target_type}", payload)
            count += 1
        return True, f"Deleted 1 {target_type}. Restored {count}."
    def get_area_at_point(self, n, x, y):
        r = self.get_robot(n)
        return next((item for item in self.get_all_robot_areas(n) if is_point_in_area(x, y, item['area'])), None) if r else None

    # --- Line / Curve / Rect Line ---
    def get_all_lines(self, n):
        r = self.get_robot(n)
        if not r: return []
        all_lines = []
        for usage in ['walls', 'tracks']:
            lines = r.get_lines(usage)
            if isinstance(lines, list):
                for l in lines: 
                    data = {"type": usage, "line": l}
                    if 'metadata' in l: data['metadata'] = l['metadata']
                    all_lines.append(data)
        return all_lines

    def create_robot_line(self, n, usage, p1, p2):
        r = self.get_robot(n)
        return r.create_line(usage, p1, p2) if r else (False, "Robot not found")

    def create_robot_curve(self, n, usage, points):
        r = self.get_robot(n)
        if not r: return False, "Robot not found"
        smooth_path = calculate_bezier_path(points, num_points=30)
        curve_id = str(uuid.uuid4())
        metadata = {"created_by": "gradio_curve", "curve_id": curve_id}
        
        lines_list = []
        for i in range(len(smooth_path)-1):
            p_start = smooth_path[i]
            p_end = smooth_path[i+1]
            dist = math.hypot(p_end['x'] - p_start['x'], p_end['y'] - p_start['y'])
            if dist > 0.01: 
                lines_list.append({
                    "start": {"x": p_start['x'], "y": p_start['y']},
                    "end": {"x": p_end['x'], "y": p_end['y']},
                    "metadata": metadata
                })
        
        if not lines_list: return False, "Curve too short"
        success, msg = r.create_lines_batch(usage, lines_list)
        return success, f"Created Curve ({len(lines_list)} segments)"

    def create_robot_rect_line(self, n, usage, p1, p2):
        r = self.get_robot(n)
        if not r: return False, "Robot not found"
        rect_id = str(uuid.uuid4())
        metadata = {"created_by": "gradio_rect", "rect_id": rect_id}
        min_x, max_x = min(p1['x'], p2['x']), max(p1['x'], p2['x'])
        min_y, max_y = min(p1['y'], p2['y']), max(p1['y'], p2['y'])
        
        lines = [
            {"start": {'x': min_x, 'y': min_y}, "end": {'x': max_x, 'y': min_y}, "metadata": metadata},
            {"start": {'x': max_x, 'y': min_y}, "end": {'x': max_x, 'y': max_y}, "metadata": metadata},
            {"start": {'x': max_x, 'y': max_y}, "end": {'x': min_x, 'y': max_y}, "metadata": metadata},
            {"start": {'x': min_x, 'y': max_y}, "end": {'x': min_x, 'y': min_y}, "metadata": metadata}
        ]
        r.create_lines_batch(usage, lines)
        return True, "Created Rect Line"

    def delete_robot_lines(self, n, usage): r=self.get_robot(n); return r.delete_lines(usage) if r else False
    def delete_line_at_point(self, n, usage, x, y):
        r = self.get_robot(n)
        if not r: return False, "Robot not found"
        lines = r.get_lines(usage)
        closest_line, min_dist = None, 0.3
        for line in lines:
            if not line or 'start' not in line or 'end' not in line: continue
            d = dist_point_to_segment(x, y, line['start']['x'], line['start']['y'], line['end']['x'], line['end']['y'])
            if d < min_dist: min_dist = d; closest_line = line
        if closest_line and 'id' in closest_line:
            del_count = 0
            meta = closest_line.get('metadata', {}) or {}
            target_group_id = meta.get('curve_id') or meta.get('rect_id')
            if target_group_id:
                for line in lines:
                    l_meta = line.get('metadata', {}) or {}
                    if l_meta.get('curve_id') == target_group_id or l_meta.get('rect_id') == target_group_id:
                        if 'id' in line:
                            r.delete_line_by_id(usage, line['id'])
                            del_count += 1
                return True, f"Deleted Group ({del_count} lines)"
            else:
                return r.delete_line_by_id(usage, closest_line['id']), f"Deleted line {closest_line['id']}"
        return False, "No line near click"

    def update_data_for_ui(self, sel_name, show_map, show_lidar_rays, show_lidar_points, show_robot, show_axis, pois, show_traj, show_path):
        r = self.get_robot(sel_name)
        j_pose, j_lidar, j_map, j_areas, j_lines = "{}", "{}", "{}", "{}", "{}"
        p_str, s_str, h_str = "No Pose", "Checking...", ""
        
        if r:
            pose = r.get_pose()
            if pose:
                p_str = f"📍 {sel_name}: {pose['x']:.2f}, {pose['y']:.2f}, {pose['yaw']:.2f}"
                if sel_name not in self.trajectories: self.trajectories[sel_name] = []
                traj = self.trajectories[sel_name]
                if not traj or math.hypot(pose['x']-traj[-1]['x'], pose['y']-traj[-1]['y']) > 0.1:
                    traj.append({'x': pose['x'], 'y': pose['y']})
                    if len(traj) > 1000: self.trajectories[sel_name].pop(0)
            
            multi = []
            for n, rb in self.robots.items():
                p = rb.get_pose()
                if p:
                    multi.append({
                        "name": n,
                        "x": p['x'],
                        "y": p['y'],
                        "yaw": p['yaw'],
                        "is_selected": (n == sel_name)
                    })
            j_pose = json.dumps({"multi_poses": multi, "visible": show_robot})
            
            scan = r.get_laser_scan() if (show_lidar_rays or show_lidar_points) else None
            j_lidar = json.dumps({"scan": scan, "pose": pose if pose else {'x':0,'y':0,'yaw':0}, "visible": True, "visible_rays": show_lidar_rays, "visible_points": show_lidar_points})
            
            planned_path = r.get_move_path() if show_path else []
            
            real_pois = r.get_pois()
            home_docks = r.get_home_docks()
            
            health = self.get_robot_health_status(sel_name)
            if health['hasError']:
                err_codes = [str(e['errorCode']) for e in health['errors']]
                h_str = f"⚠️ Error: {', '.join(err_codes)}"
            else: h_str = "✅ Healthy"

            map_url, bounds = None, None
            current_time = time.time()
            if show_map:
                if (current_time - self.last_map_update_time.get(sel_name, 0) > 1.0) or (sel_name not in self.cached_map_url):
                    raw = r.get_map_explore()
                    if raw:
                        current_hash = len(raw)
                        if self.last_map_hash.get(sel_name) != current_hash:
                            grid, meta = parse_grid_and_meta(raw)
                            if grid is not None:
                                map_url = generate_map_base64(grid)
                                bounds = [[meta['min_y'], meta['min_x']], [meta['max_y'], meta['max_x']]]
                                self.last_map_hash[sel_name] = current_hash
                                self.cached_map_url[sel_name] = (map_url, bounds)
                    self.last_map_update_time[sel_name] = current_time 
            
            cached = self.cached_map_url.get(sel_name, (None, None))
            j_map = json.dumps({
                "pois": real_pois,
                "docks": home_docks,
                "trajectory": self.trajectories.get(sel_name, []) if show_traj else [],
                "planned_path": planned_path,
                "visible_map": show_map, "visible_axis": show_axis, 
                "map_url": map_url if map_url else cached[0], "bounds": bounds if bounds else cached[1]
            })

            j_areas = json.dumps({"visible": True, "areas": self.get_all_robot_areas(sel_name)})
            j_lines = json.dumps({"visible": True, "lines": self.get_all_lines(sel_name)})
            s_str = f"Connected: {len(self.robots)}"
            
        return j_pose, j_lidar, j_map, j_areas, j_lines, p_str, s_str, h_str

manager = AMRManager()