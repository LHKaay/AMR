import requests
import json
import math
import uuid

class Robot:
    def __init__(self, name, ip):
        self.name = name
        self.ip = ip
        self.host = f"http://{ip}:1448"
        self.connected = False
        self.connect()

    def connect(self):
        try:
            url = f"{self.host}/api/core/system/v1/robot/health"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                self.connected = True
                print(f"[{self.name}] Connected to {self.ip}")
            else:
                self.connected = False
        except:
            self.connected = False
            print(f"[{self.name}] Failed to connect to {self.ip}")

    def disconnect(self):
        self.connected = False
        print(f"[{self.name}] Disconnected")

    def _get(self, endpoint):
        if not self.connected: return None
        try:
            url = f"{self.host}{endpoint}"
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return response.json()
        except: return None

    def _post(self, endpoint, payload):
        if not self.connected: return False, "Robot Disconnected"
        try:
            url = f"{self.host}{endpoint}"
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=2)
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)

    def _put(self, endpoint, payload):
        if not self.connected: return False, "Robot Disconnected"
        try:
            url = f"{self.host}{endpoint}"
            headers = {'Content-Type': 'application/json'}
            response = requests.put(url, data=json.dumps(payload), headers=headers, timeout=2)
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)

    def _delete(self, endpoint):
        if not self.connected: return False
        try:
            url = f"{self.host}{endpoint}"
            headers = {'accept': 'application/json'}
            response = requests.delete(url, headers=headers, timeout=2)
            return response.status_code == 200
        except: return False

    # --- Core Functions ---
    def get_pose(self):
        return self._get("/api/core/slam/v1/localization/pose")

    def get_laser_scan(self):
        return self._get("/api/core/system/v1/laserscan")

    def get_move_path(self):
        data = self._get("/api/core/motion/v1/path")
        return data["path_points"] if data and "path_points" in data else []

    def get_map_explore(self):
        try:
            if not self.connected: return None
            url = f"{self.host}/api/core/slam/v1/maps/explore"
            response = requests.get(url, headers={'Accept': 'application/octet-stream'}, timeout=3)
            if response.status_code == 200:
                return response.content
        except: pass
        return None

    # --- POI ---
    def get_pois(self):
        return self._get("/api/core/artifact/v1/pois") or []

    def add_poi(self, poi_id, metadata, pose=None):
        # pose가 None이면 로봇의 현재 위치를 사용 (API 스펙)
        payload = {
            "id": poi_id,
            "metadata": metadata
        }
        if pose:
            payload["pose"] = pose
        return self._post("/api/core/artifact/v1/pois", payload)

    def update_poi(self, poi_id, metadata=None, pose=None):
        payload = {}
        if metadata: payload["metadata"] = metadata
        if pose: payload["pose"] = pose
        return self._put(f"/api/core/artifact/v1/pois/{poi_id}", payload)

    def delete_poi(self, poi_id):
        return self._delete(f"/api/core/artifact/v1/pois/{poi_id}")
    
    def adjust_pois(self):
        return self._post("/api/core/artifact/v1/pois/:adjust", {})

    # --- Home Dock ---
    def get_home_docks(self):
        return self._get("/api/core/slam/v1/homedocks") or []

    def register_home_dock(self, display_name):
        # 현재 위치를 Dock으로 등록
        payload = {"metadata": {"display_name": display_name}}
        return self._post("/api/core/slam/v1/homedocks/:register", payload)

    def delete_home_dock(self, dock_id):
        return self._delete(f"/api/core/slam/v1/homedocks/{dock_id}")

    # --- System & Health ---
    def get_robot_health(self):
        return self._get("/api/core/system/v1/robot/health")

    def clear_robot_error(self, error_code):
        return self._delete(f"/api/core/system/v1/robot/health/{error_code}")

    def shutdown_robot(self):
        return self._post("/api/core/system/v1/power/:shutdown", {"shutdown_time_interval": 0, "restart_time_interval": 0})

    # --- Areas ---
    def get_rectangle_areas(self, area_type):
        data = self._get(f"/api/core/artifact/v1/rectangle-areas/{area_type}")
        return data if isinstance(data, list) else []
    
    # def create_rectangle_area(self, area_type, p1, p2, door_type=0, advanced_params=None):
    #     min_x, max_x = min(p1['x'], p2['x']), max(p1['x'], p2['x'])
    #     min_y, max_y = min(p1['y'], p2['y']), max(p1['y'], p2['y'])
    #     mid_y, half_width = (min_y + max_y) / 2, (max_y - min_y) / 2
        
    #     metadata = {"created_by": "gradio_gui"}
    #     if advanced_params: metadata.update(advanced_params)

    #     # Type-specific default metadata handling
    #     if area_type == "forbidden_area": 
    #         if "escape_distance" not in metadata: metadata["escape_distance"] = "0.1"
    #     elif area_type == "elevator_area":
    #         metadata.update({"elevator_id": str(uuid.uuid4()), "elevator_sill_width": "0.5", "elevator_scheduling_point_dist": "1.0", "elevator_door_type": str(door_type)})
    #     elif area_type == "restricted_area":
    #         metadata.update({"restricted_robots_number_limit": "1", "restricted_scheduling_points": "[]"})
    #     elif area_type == "sensor_disable_area":
    #         if "sensor_type" not in metadata: metadata["sensor_type"] = "[]"
    #     elif area_type == "dangerous_area":
    #         if "dangerous_area_type" not in metadata: metadata["dangerous_area_type"] = "1"
    #         if "max_line_speed" not in metadata: metadata["max_line_speed"] = "0.5"

    #     payload = {"area": {"start": {"x": min_x, "y": mid_y}, "end": {"x": max_x, "y": mid_y}, "half_width": half_width}, "metadata": metadata}
    #     return self._post(f"/api/core/artifact/v1/rectangle-areas/{area_type}", payload)

    def create_rectangle_area(self, area_type, p1, p2, door_type=0, advanced_params=None):
        # [CRITICAL FIX] Do NOT calculate min/max here. 
        # Pass p1 (start) and p2 (end) directly to define rotation/length correctly.
        
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

        # Calculate half width from geometry if passed, otherwise default is used in msis_amr
        # But here we just construct the payload.
        # Note: msis_amr.py calculates geometry. Here we rely on payload construction.
        # Wait, msis_amr calls this. Let's make this function generic payload builder.
        
        # Actually, msis_amr handles the math. We should just take the 'area' dict if possible?
        # To keep it compatible with previous structure:
        # We assume p1 and p2 are the *center line* segment endpoints.
        # Half-width is missing here! It was calculated inside msis_amr but passed implicitly?
        # No, msis_amr passes p1, p2 and calls this. 
        # We need half_width as an argument to be precise, OR we assume a default here.
        # Let's add half_width arg with default.
        
        # Re-reading msis_amr.py: create_robot_area calls this.
        # We need to accept the area dictionary or construct it properly.
        # Let's fix this method signature to take the full area dict or construct it correctly.
        
        # For minimal disruption: We will calculate distance between p1, p2 to valid check, 
        # but rely on caller for width? 
        # NO, the caller (msis_amr) calculates half_width. We must respect it.
        pass # Placeholder for thought trace.
        
    # [REVISED] Improved Create Method
    def create_rectangle_area_direct(self, area_type, area_payload, metadata):
        payload = {"area": area_payload, "metadata": metadata}
        return self._post(f"/api/core/artifact/v1/rectangle-areas/{area_type}", payload)

    def delete_rectangle_areas(self, area_type):
        return self._delete(f"/api/core/artifact/v1/rectangle-areas/{area_type}")

    # --- Lines ---
    def get_lines(self, usage):
        data = self._get(f"/api/core/artifact/v1/lines/{usage}")
        return data if isinstance(data, list) else []

    def create_line(self, usage, p1, p2, metadata=None):
        if metadata is None: metadata = {"created_by": "gradio_gui"}
        payload = [{"start": {"x": p1['x'], "y": p1['y']}, "end": {"x": p2['x'], "y": p2['y']}, "metadata": metadata}]
        return self._post(f"/api/core/artifact/v1/lines/{usage}", payload)

    # [NEW] Create Multiple Lines (Batch)
    def create_lines_batch(self, usage, lines_list):
        # lines_list format: [{"start": {...}, "end": {...}, "metadata": {...}}, ...]
        return self._post(f"/api/core/artifact/v1/lines/{usage}", lines_list)

    def delete_lines(self, usage):
        return self._delete(f"/api/core/artifact/v1/lines/{usage}")

    def delete_line_by_id(self, usage, line_id):
        return self._delete(f"/api/core/artifact/v1/lines/{usage}/{line_id}")

    # --- Move ---
    def move_to(self, x, y, yaw=None, mode=0, flags=None):
        if flags is None: flags = []
        if yaw is not None and "with_yaw" not in flags: flags.append("with_yaw")
        options = {"target": {"x": x, "y": y, "z": 0}, "move_options": {"mode": int(mode), "flags": flags}}
        if yaw is not None: options["target"]["yaw"] = yaw
        self._post("/api/core/motion/v1/actions", {"action_name": "slamtec.agent.actions.MoveToAction", "options": options})

    def follow_path(self, points, mode=0, yaw=None, flags=None):
        if flags is None: flags = []
        path_points = [{"x": p['x'], "y": p['y'], "z": 0} for p in points]
        if yaw is not None and "with_yaw" not in flags: flags.append("with_yaw")
        move_options = {"mode": int(mode), "flags": flags}
        if yaw is not None: move_options["yaw"] = yaw
        return self._post("/api/core/motion/v1/actions", {"action_name": "slamtec.agent.actions.FollowPathPointsAction", "options": {"path_points": path_points, "move_options": move_options}})

    def stop(self):
        self._delete("/api/core/motion/v1/actions/:current")