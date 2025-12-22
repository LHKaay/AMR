import requests
import sqlite3
import os

# ---------------------------------------------------------
# 개별 로봇 제어 클래스 (HTTP API)
# ---------------------------------------------------------
class MSISRobot:
    def __init__(self, name, ip, port="1448"):
        self.name = name
        self.ip = ip
        self.port = str(port)
        self.base_url = f"http://{ip}:{port}"
        self.session = requests.Session()
        self.timeout = 0.2

    def _get(self, endpoint):
        try:
            response = self.session.get(self.base_url + endpoint, timeout=self.timeout)
            if response.status_code == 200:
                if 'application/json' in response.headers.get('Content-Type', ''):
                    return response.json()
                return response.content
            return None
        except requests.exceptions.Timeout:
            # print(f"[{self.name}] Timeout Error") # 타임아웃 명시
            return None
        except Exception as e:
            # print(f"[{self.name}] Connection Error: {e}") # 그 외 에러 출력
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
    def get_pose(self): return self._get("/api/core/slam/v1/localization/pose")
    def get_map_explore(self): return self._get("/api/core/slam/v1/maps/explore")
    def get_health(self): return self._get("/api/core/system/v1/robot/health")
    def get_base_status(self): return self._get("/api/core/system/v1/base/status")
    def get_laser_scan(self): return self._get("/api/core/system/v1/laserscan")
    def get_rectangle_areas(self, usage="forbidden_area"): 
        res = self._get(f"/api/core/artifact/v1/rectangle-areas/{usage}")
        return res if res else []
    
    def add_rectangle_area(self, usage, p1, p2):
        payload = {
            "area": {"start": {"x": float(p1[0]), "y": float(p1[1])}, "end": {"x": float(p2[0]), "y": float(p2[1])}, "half_width": 0.0},
            "metadata": {"escape_distance": "0.2"}
        }
        return self._post(f"/api/core/artifact/v1/rectangle-areas/{usage}", data=payload)

    def get_pois(self):
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
    
    # [수정] Yaw 인자 제거 (도착 후 회전 방지)
    def move_to(self, x, y):
        payload = {
            "action_name": "slamtec.agent.actions.MoveToAction",
            "options": {
                "target": {"x": float(x), "y": float(y), "z": 0},
                "move_options": {
                    "mode": 0
                    # flags: ["with_yaw"] 제거됨
                }
            }
        }
        return self._post("/api/core/motion/v1/actions", data=payload)
    
    def stop(self): return self._delete("/api/core/motion/v1/actions/:current")


# ---------------------------------------------------------
# AMR Manager (SQLite)
# ---------------------------------------------------------
class AMRManager:
    def __init__(self, db_file="robots.db"):
        self.db_file = db_file
        self.robots = {} 
        self.init_db()
        self.load_from_db()

    def init_db(self):
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
        self.robots = {}
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, ip, port FROM robots")
            rows = cursor.fetchall()
            
            if not rows:
                self.add_robot("AMR_01", "192.168.0.132")
            else:
                for name, ip, port in rows:
                    self.robots[name] = MSISRobot(name, ip, port)

    def add_robot(self, name, ip, port="1448"):
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
        return self.robots.get(name)

    def get_all_robots(self):
        return self.robots

manager = AMRManager()