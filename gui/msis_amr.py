# gui/msis_amr.py
import os
import threading
import time
import sqlite3
import json  # For UI data transmission
from .rest_api import Robot

class AMRManager:
    def __init__(self):
        self.robots = {}  # Robot objects currently loaded in memory {name: Robot}
        
        # 1. Set the DB file path (robot.db in the parent folder where main.py is located)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        self.db_file = os.path.join(root_dir, "robot.db")
        
        # 2. Initialize and load DB
        self._init_db()
        self.load_db()

    # --- [Database Logic] ---
    def _init_db(self):
        """Create DB table if it does not exist"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            # Create a table (name is unique key)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS robots (
                    name TEXT PRIMARY KEY, 
                    ip TEXT NOT NULL
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ DB Init Error: {e}")

    def load_db(self):
        """Read the robot list from the DB and load it into memory (self.robots)"""
        if not os.path.exists(self.db_file):
            print("⚠️ robot.db file not found.")
            return

        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT name, ip FROM robots")
            rows = cursor.fetchall()
            conn.close()

            for name, ip in rows:
                # When loading from DB, there is no need to save DB again (db_sync=False)
                self.add_robot(name, ip, db_sync=False)
            
            print(f"✅ Loaded {len(self.robots)} robots from robot.db")
        except Exception as e:
            print(f"❌ Error loading DB: {e}")

    def _save_to_db(self, name, ip):
        """Add or update robots to the DB (INSERT OR REPLACE)"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO robots (name, ip) VALUES (?, ?)", (name, ip))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ DB Save Error: {e}")

    def _delete_from_db(self, name):
        """Delete robot from DB"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM robots WHERE name=?", (name,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ DB Delete Error: {e}")

    # --- [Manager Logic] ---
    def add_robot(self, name, ip, db_sync=True):
        """
        Add a robot or edit its information. 
        If the name already exists, disconnect it and update the information.
        """
        # If it exists, disconnect it (to update information)
        if name in self.robots:
            self.robots[name].disconnect()
        
        # Attempt to create and connect a new robot object
        self.robots[name] = Robot(name, ip)
        
        # DB sync (True only when added in UI)
        if db_sync:
            self._save_to_db(name, ip)
            
        return self.get_robot_names()

    def delete_robot(self, name):
        """로봇을 목록과 DB에서 삭제합니다."""
        if name in self.robots:
            self.robots[name].disconnect()
            del self.robots[name]
            self._delete_from_db(name)
            print(f"🗑️ Deleted robot: {name}")
        return self.get_robot_names()

    def get_robot(self, name):
        return self.robots.get(name)

    def get_all_robots(self):
        return self.robots

    def get_robot_names(self):
        return list(self.robots.keys())

    # --- [Control Logic] Movement & Actions ---
    def manual_move(self, name, code):
        r = self.get_robot(name)
        if r:
            payload = { "action_name": "slamtec.agent.actions.MoveByAction", "options": { "direction": code, "duration": 500 } }
            r._post("/api/core/motion/v1/actions", payload)

    def cmd_stop(self, name):
        r = self.get_robot(name)
        if r: r.stop()

    def trigger_motion_thread(self, robot_name, waypoint_list, mode):
        r = self.get_robot(robot_name)
        if not r: return "Robot not found"
        
        def run():
            if mode == "path":
                for pt in waypoint_list:
                    r.move_to(pt['x'], pt['y'])
                    time.sleep(3.0) 
            elif mode == "ortho":
                if not waypoint_list: return
                target = waypoint_list[-1]
                curr = r.get_pose()
                if curr:
                    r.move_to(target['x'], curr['y'])
                    time.sleep(3.0)
                    r.move_to(target['x'], target['y'])
        
        threading.Thread(target=run).start()
        return f"Started {mode} move."

    def update_data_for_ui(self, selected_robot_name, show_map, show_laser, show_robot, show_axis, poi_list):
        """Generate data for UI refresh"""
        target_robot = self.get_robot(selected_robot_name)
        j_pose, j_lidar, j_map = "{}", "{}", "{}"
        pose_str, status_str = "No Pose", "Checking..."

        if target_robot:
            pose = target_robot.get_pose()
            multi_poses = []
            
            for name, r in self.robots.items():
                p = r.get_pose()
                if p:
                    multi_poses.append({
                        "name": name, 
                        "x": p["x"], "y": p["y"], "yaw": p["yaw"], 
                        "is_selected": (name == selected_robot_name), 
                        "has_error": False
                    })
            j_pose = json.dumps({"multi_poses": multi_poses, "visible": show_robot})

            scan = target_robot.get_laser_scan() if show_laser else None
            j_lidar = json.dumps({"scan": scan, "pose": pose, "visible": show_laser})
            
            final_pois = target_robot.get_pois() + (poi_list if poi_list else [])
            j_map = json.dumps({
                "pois": final_pois, 
                "areas": target_robot.get_rectangle_areas("forbidden_area"), 
                "visible_map": show_map, 
                "visible_axis": show_axis,
                "map_url": None, "bounds": None
            })
            
            if pose:
                pose_str = f"📍 {selected_robot_name}: {pose['x']:.2f}, {pose['y']:.2f}"
            status_str = f"Connected: {len(self.robots)}"
        
        return j_pose, j_lidar, j_map, pose_str, status_str

# 전역 인스턴스 생성
manager = AMRManager()