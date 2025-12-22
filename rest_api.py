import requests
import json

# ---------------------------------------------------------
# Existing MSISRobot Class (From your provided api.py)
# ---------------------------------------------------------
class MSISRobot:
    """
    Class handling HTTP API communication with the AMR.
    Keeps existing logic intact.
    """
    def __init__(self, name, ip, port="1448"):
        self.name = name
        self.ip = ip
        self.port = str(port)
        self.base_url = f"http://{ip}:{port}"
        self.session = requests.Session()
        self.timeout = 0.5 # Increased timeout slightly for stability

    def _get(self, endpoint):
        try:
            response = self.session.get(self.base_url + endpoint, timeout=self.timeout)
            if response.status_code == 200:
                if 'application/json' in response.headers.get('Content-Type', ''):
                    return response.json()
                return response.content
            return None
        except requests.exceptions.Timeout:
            # print(f"[{self.name}] Timeout Error") 
            return None
        except Exception as e:
            # print(f"[{self.name}] Connection Error: {e}")
            return None

    def _post(self, endpoint, data=None):
        try:
            headers = {'Content-Type': 'application/json'}
            response = self.session.post(self.base_url + endpoint, json=data, headers=headers, timeout=self.timeout)
            return response.json() if response.status_code == 200 else None
        except: return None
            
    def _delete(self, endpoint):
        try:
            response = self.session.delete(self.base_url + endpoint, timeout=self.timeout)
            return response.json() if response.status_code == 200 else None
        except: return None

    # --- Essential Functions (Existing) ---
    def get_pose(self): 
        """Returns the robot's current pose (x, y, yaw)."""
        return self._get("/api/core/slam/v1/localization/pose")
    
    def get_map_data(self): 
        """Returns the raw grid map data (bytes)."""
        return self._get("/api/core/slam/v1/maps/explore")
    
    def get_health(self): return self._get("/api/core/system/v1/robot/health")
    def get_laser_scan(self): return self._get("/api/core/system/v1/laserscan")
    
    def get_rectangle_areas(self, usage="forbidden_area"): 
        res = self._get(f"/api/core/artifact/v1/rectangle-areas/{usage}")
        return res if res else []
    
    def add_rectangle_area(self, usage, p1, p2):
        """Adds a rectangular area (e.g., forbidden zone)."""
        payload = {
            "area": {"start": {"x": float(p1[0]), "y": float(p1[1])}, "end": {"x": float(p2[0]), "y": float(p2[1])}, "half_width": 0.0},
            "metadata": {"escape_distance": "0.2"}
        }
        return self._post(f"/api/core/artifact/v1/rectangle-areas/{usage}", data=payload)

    def move_to(self, x, y):
        """Moves the robot to a specific coordinate."""
        payload = {
            "action_name": "slamtec.agent.actions.MoveToAction",
            "options": {
                "target": {"x": float(x), "y": float(y), "z": 0},
                "move_options": { "mode": 0 }
            }
        }
        return self._post("/api/core/motion/v1/actions", data=payload)
    
    def stop(self): return self._delete("/api/core/motion/v1/actions/:current")
    
    def get_action_status(self):
        """Checks if the robot is currently performing an action."""
        return self._get("/api/core/motion/v1/actions")


# ---------------------------------------------------------
# Wrapper Functions (Requested Requirements)
# ---------------------------------------------------------

def connect_to_amr(ip, port="1448", name="AMR_Main"):
    """
    Establishes a connection logic by creating a robot instance.
    Real connection is stateless (HTTP), but this initializes the handler.
    """
    robot = MSISRobot(name, ip, port)
    # Check health to verify connection
    health = robot.get_health()
    if health:
        print(f"Successfully connected to {name} ({ip})")
        return robot
    else:
        print(f"Failed to connect to {name} ({ip})")
        return None

def get_map_data(robot):
    """Wraps the get_map_explore function."""
    return robot.get_map_explore()

def get_current_position(robot):
    """Wraps the get_pose function."""
    return robot.get_pose()

def start_mapping_mode(robot):
    """Sets the robot to mapping mode."""
    return robot._post("/api/core/slam/v1/mode", {"mode": "mapping"})