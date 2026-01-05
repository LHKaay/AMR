import json
import math
import csv
import gradio as gr
from . import gui_map_utils
from .msis_amr import manager

# ... (Constants 유지) ...
AREA_TYPES = ["forbidden_area", "elevator_area", "dangerous_area", "coverage_area", "maintenance_area", "sensor_disable_area", "restricted_area"]
ARTIFACT_TYPES = ["walls", "tracks"]
TRACK_MOVE_MODES = [("2: Rail Priority (Detour)", 2), ("1: Strict Rail (Stop)", 1)]
MODE_NAV = "nav"
MODE_DRAW_AREA = "draw_area"
MODE_DRAW_LINE = "draw_line"
MODE_DRAW_CURVE = "draw_curve"
MODE_DRAW_RECT_LINE = "draw_rect_line"
DOOR_TYPE_MAP = {"Front Door": 0, "Rear Door": 1, "Double Doors": 2}

def format_dashboard(pose_str, status_str, target_str, health_str):
    robot_name, x, y, yaw, conn_count, target_display = "Unknown", "0.00", "0.00", "0.00", "0", "—"
    if "Connected:" in status_str: conn_count = status_str.split(":")[-1].strip()
    if "📍" in pose_str:
        try:
            parts = pose_str.replace("📍", "").split(":")
            robot_name = parts[0].strip()
            if len(parts) > 1:
                vals = parts[1].split(",")
                if len(vals) >= 3: x, y, yaw = vals[0].strip(), vals[1].strip(), vals[2].strip()
        except: pass
    elif pose_str == "No Pose": robot_name = "Offline"
    if "Target:" in target_str:
        val = target_str.split("Target:")[1].strip()
        if val and val != "None": target_display = val
    
    return f"""[Connected Robots] : {conn_count}
[{robot_name} Status]
Pose: x={x} m | y={y} m | yaw={yaw} rad
Health: {health_str}
Click to Map Position : {target_display}"""

def on_clear_error(r_name):
    if not r_name: return "No Robot"
    health = manager.get_robot_health_status(r_name)
    if health['hasError']:
        for e in health['errors']:
            manager.clear_robot_error(r_name, e['errorCode'])
        return "Errors Cleared"
    return "No Errors to Clear"

def on_shutdown(r_name):
    if not r_name: return "No Robot"
    manager.shutdown_robot(r_name)
    return "Shutdown Sent"

def on_set_axis_zero(r_name):
    if not r_name: return "No Robot Selected"
    r = manager.get_robot(r_name)
    if not r: return "Robot Not Found"
    curr = r.get_pose()
    if not curr: return "Failed to get current pose"
    success, msg = manager.set_robot_pose(r_name, curr['x'], curr['y'], 0.0)
    return "Axis Aligned (Yaw=0)" if success else f"Failed: {msg}"

# -- dock --- #
def on_register_dock(r_name, name):
    if not r_name or not name: return "Enter Name"
    manager.register_home_dock(r_name, name)
    return f"Registered Dock: {name}"

def on_delete_dock(r_name, dock_str):
    if not r_name or not dock_str: return "Select Dock"
    target_id = dock_str
    if "(" in dock_str and dock_str.endswith(")"):
        target_id = dock_str.split("(")[-1].strip(")")
    manager.delete_home_dock(r_name, target_id)
    return f"Deleted Dock {target_id}"

def on_go_home(r_name):
    if not r_name: return "No Robot"
    return manager.go_home(r_name)

def get_dock_list(r_name):
    if not r_name: return []
    docks = manager.get_home_docks(r_name)
    return [f"{d.get('metadata',{}).get('display_name','Dock')} ({d['id']})" for d in docks]

def refresh_dock_choices(r_name):
    return gr.update(choices=get_dock_list(r_name))

# -- POI --- #
def get_poi_list(r_name):
    if not r_name: return []
    pois = manager.get_pois(r_name)
    result = []
    for p in pois:
        meta = p.get('metadata', {})
        name = meta.get('display_name', 'POI')
        ptype = meta.get('type', 'Unknown')
        pid = p.get('id')
        result.append(f"{name} ({ptype}) [{pid}]")
    return result

def refresh_poi_choices_api(r_name):
    return gr.update(choices=get_poi_list(r_name))

def on_delete_poi(r_name, poi_str):
    if not r_name or not poi_str: return "Select POI"
    try:
        target_id = poi_str.split("[")[-1].strip("]")
        success = manager.delete_poi(r_name, target_id)
        return f"Deleted POI {target_id}" if success else "Failed to delete"
    except: return "Invalid POI Selection"

def on_add_poi_at_robot(r_name, name, ptype):
    if not r_name or not name: return "Enter Name", gr.update()
    success, msg = manager.add_poi(r_name, name, ptype, use_robot_pose=True)
    return f"Add Result: {msg}", refresh_poi_choices_api(r_name)

# [NEW] Add POI at Click Location (Yaw 0)
def on_add_poi_at_click(r_name, name, ptype, click_json):
    if not r_name or not name: return "Enter Name", gr.update()
    if not click_json: return "Click Map First", gr.update()
    try:
        pt = json.loads(click_json)
        # Force Yaw 0
        success, msg = manager.add_poi(r_name, name, ptype, use_robot_pose=False, x=pt['x'], y=pt['y'], yaw=0.0)
        return f"Added POI at click: {msg}", refresh_poi_choices_api(r_name)
    except: return "Invalid Click Data", gr.update()

def on_adjust_pois(r_name):
    if not r_name: return "No Robot"
    success, msg = manager.adjust_pois(r_name)
    return "Adjustment Started" if success else f"Adjustment Failed: {msg}"

# [UPDATED] Select POI and populate Yaw
def on_poi_select_for_edit(r_name, poi_str):
    if not r_name or not poi_str: return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), "Select POI"
    try:
        target_id = poi_str.split("[")[-1].strip("]")
        pois = manager.get_pois(r_name)
        target = next((p for p in pois if p['id'] == target_id), None)
        if target:
            meta = target.get('metadata', {})
            pose = target.get('pose', {})
            return (
                gr.update(value=target_id),
                gr.update(value=meta.get('display_name', '')),
                gr.update(value=meta.get('type', 'Generic')),
                gr.update(value=pose.get('x', 0)),
                gr.update(value=pose.get('y', 0)),
                gr.update(value=pose.get('yaw', 0)), # Load Yaw
                f"Loaded POI: {target_id}"
            )
    except: pass
    return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), "POI Not Found"

# [UPDATED] Confirm Update with Yaw
def on_update_poi_confirm(r_name, poi_id, name, ptype, x, y, yaw):
    if not r_name or not poi_id: return "Load POI first", gr.update()
    success, msg = manager.update_poi(r_name, poi_id, name, ptype, x, y, yaw)
    return f"Update Result: {msg}", refresh_poi_choices_api(r_name)

# ... (Area functions) ...
def on_area_type_change(atype):
    is_elevator = (atype == "elevator_area")
    is_dangerous = (atype == "dangerous_area")
    is_sensor_disable = (atype == "sensor_disable_area")
    return [gr.update(visible=is_elevator), gr.update(visible=is_dangerous), gr.update(visible=is_sensor_disable)]

def calc_geometry_from_points(p1, p2, half_width):
    cx = (p1['x'] + p2['x']) / 2; cy = (p1['y'] + p2['y']) / 2
    dx = p2['x'] - p1['x']; dy = p2['y'] - p1['y']
    length = math.hypot(dx, dy); width = half_width * 2; rotation = math.atan2(dy, dx)
    return cx, cy, length, width, rotation

def calc_points_from_geometry(cx, cy, length, width, rotation):
    half_len = length / 2; dx = half_len * math.cos(rotation); dy = half_len * math.sin(rotation)
    start = {'x': cx - dx, 'y': cy - dy}; end = {'x': cx + dx, 'y': cy + dy}
    return start, end

def on_edit_click(r_name, selected_area_json):
    if not selected_area_json: return [gr.update()] * 7 + ["Select area first"]
    try:
        area_data = json.loads(selected_area_json)
        atype = area_data.get('type', 'forbidden_area')
        door_val = "Front Door"
        meta = area_data.get('metadata', {})
        if 'elevator_door_type' in meta:
            dtype = meta['elevator_door_type']
            if dtype == '1': door_val = "Rear Door"
            elif dtype == '2': door_val = "Double Doors"
        area = area_data['area']
        p1, p2 = area['start'], area['end']; hw = area['half_width']
        cx, cy, length, width, rot = calc_geometry_from_points(p1, p2, hw)
        return gr.update(value=atype), gr.update(value=door_val), gr.update(value=cx), gr.update(value=cy), gr.update(value=length), gr.update(value=width), gr.update(value=rot), gr.update(visible=True), f"Editing {atype}..."
    except: return [gr.update()] * 7 + ["Error"]

def on_confirm_area(r_name, atype, door_str, cx, cy, length, width, rotation, 
                   danger_type, max_speed, sensor_checks, 
                   selected_area_json):
    if not r_name: return gr.update(), gr.update(), gr.update(), gr.update(visible=False), [], None
    if selected_area_json:
        try:
            old = json.loads(selected_area_json)
            manager.delete_area_at_point(r_name, old['area']['start']['x'], old['area']['start']['y'])
        except: pass
        
    start, end = calc_points_from_geometry(cx, cy, length, width, rotation)
    door_int = DOOR_TYPE_MAP.get(door_str, 0)
    
    adv_params = {}
    if atype == "dangerous_area":
        adv_params["dangerous_area_type"] = 0 if danger_type == "Slope" else 1 
        adv_params["max_line_speed"] = max_speed
    elif atype == "sensor_disable_area":
        sensor_map = {"Sonar": 2, "Bumper": 0, "Cliff": 1, "Depth Camera": 3, "TOF Cliff": 4} 
        adv_params["sensor_type"] = [sensor_map[s] for s in sensor_checks if s in sensor_map]
        
    success, msg = manager.create_robot_area(r_name, atype, start, end, door_type=door_int, advanced_params=adv_params)
    areas = manager.get_all_robot_areas(r_name)
    res_msg = f"✅ Saved {atype}" if success else f"❌ Failed: {msg}"
    return json.dumps({"visible": True, "areas": areas}), res_msg, json.dumps({"clicks": []}), gr.update(visible=False), [], None

def on_cancel_area(): return "Canceled.", json.dumps({"clicks": []}), gr.update(visible=False), [], None

# --- [Main Map Click] ---
def master_map_click(coords_str, current_mode, c_list, r_name, a_type, l_type, curr_pose, curr_status, curr_health,
                     door_str, danger_type, max_speed, sensor_checks):
    default_ret = [gr.update()] * 21
    if not coords_str: return default_ret
    try:
        pt = json.loads(coords_str)
        coord_text = f"X: {pt['x']:.2f}, Y: {pt['y']:.2f}"
        new_target_str = f"🎯 Target: {coord_text}"
        new_dash = format_dashboard(curr_pose, curr_status, new_target_str, curr_health)
        
        def make_ret(clicks=[], mode=current_mode, msg="", nav_msg="", res_msg="", j_areas=gr.update(), j_lines=gr.update(), j_temp=gr.update(), sel_area=None, edit_vis=gr.update()):
             return (pt, clicks, mode, msg, coord_text, coord_text, new_target_str, new_dash, 
                     j_areas, j_lines, res_msg, j_temp, clicks, gr.update(), sel_area, edit_vis,
                     gr.update(), gr.update(), gr.update(), gr.update(), gr.update())

        if current_mode == MODE_NAV:
            selected_area = manager.get_area_at_point(r_name, pt['x'], pt['y'])
            sel_json = json.dumps(selected_area) if selected_area else None
            msg = f"Selected: {selected_area['type']}" if selected_area else "### Mode: Navigation"
            return make_ret(clicks=c_list, msg=msg, sel_area=sel_json, edit_vis=gr.update(visible=False))
        
        else:
            new_clicks = c_list + [pt]
            
            if current_mode == MODE_DRAW_CURVE:
                msg = f"### Drawing Curve... {len(new_clicks)} points. Click 'Finish' when done."
                return make_ret(clicks=new_clicks, msg=msg, j_temp=json.dumps({"clicks": new_clicks}))

            if len(new_clicks) < 2:
                return make_ret(clicks=new_clicks, msg="### Mode: Drawing... Click 2nd point.", j_temp=json.dumps({"clicks": new_clicks}))
            else:
                msg, j_lines, j_areas = "", gr.update(), gr.update()
                
                if current_mode == MODE_DRAW_LINE:
                    success, txt = manager.create_robot_line(r_name, l_type, new_clicks[0], new_clicks[1])
                    msg = f"Created Line: {txt}"
                    j_lines = json.dumps({"visible": True, "lines": manager.get_all_lines(r_name)})
                
                elif current_mode == MODE_DRAW_RECT_LINE:
                    success, txt = manager.create_robot_rect_line(r_name, l_type, new_clicks[0], new_clicks[1])
                    msg = f"Created Rect: {txt}"
                    j_lines = json.dumps({"visible": True, "lines": manager.get_all_lines(r_name)})

                elif current_mode == MODE_DRAW_AREA:
                    door_int = DOOR_TYPE_MAP.get(door_str, 0)
                    adv_params = {}
                    if a_type == "dangerous_area":
                        adv_params["dangerous_area_type"] = 0 if danger_type == "Slope" else 1 
                        adv_params["max_line_speed"] = max_speed
                    elif a_type == "sensor_disable_area":
                        sensor_map = {"Sonar": 2, "Bumper": 0, "Cliff": 1, "Depth Camera": 3, "TOF Cliff": 4} 
                        adv_params["sensor_type"] = [sensor_map[s] for s in sensor_checks if s in sensor_map]
                        
                    # p1, p2 are now Top-Left / Bottom-Right corners of bounding box
                    success, txt = manager.create_robot_area(r_name, a_type, new_clicks[0], new_clicks[1], door_type=door_int, advanced_params=adv_params)
                    msg = f"Created {a_type}: {txt}"
                    j_areas = json.dumps({"visible": True, "areas": manager.get_all_robot_areas(r_name)})
                
                return make_ret(clicks=[], mode=MODE_NAV, msg=f"### Mode: Navigation ({msg})", res_msg=msg, j_lines=j_lines, j_areas=j_areas, j_temp=json.dumps({"clicks": []}))

    except Exception as e:
        print(f"Click Error: {e}")
        return default_ret

def on_finish_curve(r_name, ltype, points):
    if not r_name: return gr.update(), "No Robot", [], gr.update()
    if len(points) < 2: return gr.update(), "Need at least 2 points", [], gr.update()
    
    success, msg = manager.create_robot_curve(r_name, ltype, points)
    j_lines = json.dumps({"visible": True, "lines": manager.get_all_lines(r_name)})
    
    return j_lines, msg, [], MODE_NAV, "###  Mode: Navigation (Curve Created)", json.dumps({"clicks": []})

def start_curve_mode(): return (MODE_DRAW_CURVE, [], "### Mode: Drawing Curve")
def start_area_mode(): return (MODE_DRAW_AREA, [], "### Mode: Drawing Area")
def start_line_mode(): return (MODE_DRAW_LINE, [], "### Mode: Drawing Line")
def start_rect_line_mode(): return (MODE_DRAW_RECT_LINE, [], "### Mode: Drawing Rect Line")

def add_robot_wrapper(n, i):
    new_list = manager.add_robot(n, i)
    return gr.update(choices=new_list, value=n), gui_map_utils.get_map_view(n, manager)
def on_free_move(r_name, target):
    if not target: return "Click map first!"
    return manager.execute_single_move(r_name, target['x'], target['y'], None, 0)
def on_track_move(r_name, target, mode):
    if not target: return "Click map first!"
    return manager.execute_track_move(r_name, target['x'], target['y'], mode)
def refresh_map(r_name): return gui_map_utils.get_map_view(r_name, manager)

def on_delete_selected_area(r_name, click_json):
    if not r_name or not click_json: return gr.update(), "Click map first"
    pt = json.loads(click_json)
    success, msg = manager.delete_area_at_point(r_name, pt['x'], pt['y'])
    areas = manager.get_all_robot_areas(r_name)
    return json.dumps({"visible":True,"areas":areas}), msg
def del_areas(n, t): 
    manager.delete_robot_areas(n, t)
    return json.dumps({"visible":True,"areas":manager.get_all_robot_areas(n)})

def on_get_lines(r_name):
    if not r_name: return json.dumps({"visible":False,"lines":[]}), "No Robot"
    lines = manager.get_all_lines(r_name)
    return json.dumps({"visible":True,"lines":lines}), f"Loaded {len(lines)} Lines"
def on_delete_type_lines(r_name, ltype):
    if not r_name: return gr.update(), "No Robot"
    manager.delete_robot_lines(r_name, ltype)
    lines = manager.get_all_lines(r_name)
    return json.dumps({"visible":True,"lines":lines}), f"Deleted {ltype}"
def on_delete_line_at_point(r_name, ltype, click_json):
    if not r_name or not click_json: return gr.update(), "Click map first"
    try:
        pt = json.loads(click_json)
        success, msg = manager.delete_line_at_point(r_name, ltype, pt['x'], pt['y'])
        lines = manager.get_all_lines(r_name)
        return json.dumps({"visible":True,"lines":lines}), msg
    except Exception as e:
        return gr.update(), f"Error: {e}"
    
def update_ui_wrapper(sel_name, s_map, s_rays, s_points, s_robot, s_axis, pois, s_traj, s_path, curr_target, curr_pose, curr_status, curr_health):
    ret = manager.update_data_for_ui(sel_name, s_map, s_rays, s_points, s_robot, s_axis, pois, s_traj, s_path)
    new_p_str, new_s_str, new_h_str = ret[5], ret[6], ret[7]
    new_dash = gr.update()
    if new_p_str != curr_pose or new_s_str != curr_status or new_h_str != curr_health:
        new_dash = format_dashboard(new_p_str, new_s_str, curr_target, new_h_str)
    
    show_clear_btn = gr.update(visible=("Error" in new_h_str))
    
    return ret[0], ret[1], ret[2], ret[3], ret[4], new_dash, new_p_str, new_s_str, new_h_str, show_clear_btn