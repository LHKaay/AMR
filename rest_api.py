import requests
import sqlite3
import os
import json

# ---------------------------------------------------------
# 1. Individual Robot Control Class (HTTP API)
# ---------------------------------------------------------
class MSISRobot:
    def __init__(self, name, ip, port="1448"):
        self.name = name
        self.ip = ip
        self.port = str(port)
        self.base_url = f"http://{ip}:{port}"
        self.session = requests.Session()
        self.timeout = 0.5  # Increased timeout for stability

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

    # --- Essential Functions ---
    def get_pose(self): 
        """Returns the robot's current pose (x, y, yaw)."""
        return self._get("/api/core/slam/v1/localization/pose")
    
    def get_map_explore(self): 
        """Returns the raw grid map data (bytes)."""
        return self._get("/api/core/slam/v1/maps/explore")
    
    def get_health(self): 
        """Returns the robot health status."""
        return self._get("/api/core/system/v1/robot/health")
    
    def get_base_status(self): 
        """Returns the base status."""
        return self._get("/api/core/system/v1/base/status")
    
    def get_laser_scan(self): 
        """Returns laser scan data."""
        return self._get("/api/core/system/v1/laserscan")
    
    def get_action_status(self):
        """Checks the current action status (to determine if moving)."""
        return self._get("/api/core/motion/v1/actions")

    def get_rectangle_areas(self, usage="forbidden_area"): 
        """Returns a list of rectangle areas (e.g., forbidden zones)."""
        res = self._get(f"/api/core/artifact/v1/rectangle-areas/{usage}")
        return res if res else []
    
    def add_rectangle_area(self, usage, p1, p2):
        """Adds a rectangular area."""
        payload = {
            "area": {"start": {"x": float(p1[0]), "y": float(p1[1])}, "end": {"x": float(p2[0]), "y": float(p2[1])}, "half_width": 0.0},
            "metadata": {"escape_distance": "0.2"}
        }
        return self._post(f"/api/core/artifact/v1/rectangle-areas/{usage}", data=payload)

    def get_pois(self):
        """Returns the list of POIs (Points of Interest)."""
        raw = self._get("/api/core/artifact/v1/pois")
        if not raw: return []
        formatted = []
        for p in raw:
            formatted.append({
                "name": p.get("name"),
                "x": p["pose"]["x"],
                "y": p["pose"]["y"],
                "yaw": p["pose"].get("yaw", 0.0),
                "type": p.get("type", "common")
            })
        return formatted
    
    def move_to(self, x, y):
        """Moves the robot to the specified coordinates."""
        payload = {
            "action_name": "slamtec.agent.actions.MoveToAction",
            "options": {
                "target": {"x": float(x), "y": float(y), "z": 0},
                "move_options": { "mode": 0 }
            }
        }
        return self._post("/api/core/motion/v1/actions", data=payload)
    
    def stop(self): 
        """Stops the current action."""
        return self._delete("/api/core/motion/v1/actions/:current")


# ---------------------------------------------------------
# 2. AMR Manager (SQLite DB Management)
# ---------------------------------------------------------
class AMRManager:
    def __init__(self, db_file="robots.db"):
        self.db_file = db_file
        self.robots = {} 
        self.init_db()
        self.load_from_db()

    def init_db(self):
        """Initializes the SQLite database."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS robots (
                    name TEXT PRIMARY KEY,
                    ip TEXT NOT NULL,
                    port TEXT DEFAULT '1448'
                )
            ''')
            conn.commit()

    def load_from_db(self):
        """Loads robots from the database into memory."""
        self.robots = {}
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, ip, port FROM robots")
            rows = cursor.fetchall()
            
            if not rows:
                # Default initial value
                self.add_robot("AMR_Main", "192.168.0.132")
            else:
                for name, ip, port in rows:
                    self.robots[name] = MSISRobot(name, ip, port)

    def add_robot(self, name, ip, port="1448"):
        """Adds a robot to the database and memory."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO robots (name, ip, port) VALUES (?, ?, ?)", (name, ip, port))
                conn.commit()
            self.robots[name] = MSISRobot(name, ip, port)
            return list(self.robots.keys())
        except Exception as e:
            print(f"DB Error: {e}")
            return list(self.robots.keys())

    def delete_robot(self, name):
        """Removes a robot from the database and memory."""
        if name in self.robots:
            try:
                with sqlite3.connect(self.db_file) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM robots WHERE name = ?", (name,))
                    conn.commit()
                del self.robots[name]
            except: pass
        return list(self.robots.keys())

    def get_robot(self, name):
        """Retrieves a robot instance by name."""
        return self.robots.get(name)

    def get_all_robots(self):
        """Returns all managed robots."""
        return self.robots

# Create Singleton Manager Instance
manager = AMRManager()


# ---------------------------------------------------------
# 3. Helper Function for Connection (Backward Compatibility)
# ---------------------------------------------------------
def connect_to_amr(ip, port="1448", name="AMR_Main"):
    """
    Connects to a single robot for compatibility with existing code.
    Registers or retrieves the robot via the Manager.
    """
    # Check if exists in manager, else add
    existing = manager.get_robot(name)
    if existing and existing.ip == ip:
        robot = existing
    else:
        manager.add_robot(name, ip, port)
        robot = manager.get_robot(name)
    
    # Connection test
    if robot.get_health():
        print(f"Successfully connected to {name} ({ip})")
        return robot
    else:
        print(f"Failed to connect to {name} ({ip})")
        return None