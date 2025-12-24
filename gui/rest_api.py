import requests
import json
import math

# 로봇 개별 통신을 담당하는 클래스
class Robot:
    def __init__(self, name, ip):
        self.name = name
        self.ip = ip
        self.host = f"http://{ip}:1448"
        self.connected = False
        # 연결 확인 (생성 시 시도)
        self.connect()

    def connect(self):
        """로봇 연결 시도 (Health Check)"""
        try:
            # 간단한 API 호출로 연결 확인
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
        """로봇 연결 해제 처리"""
        self.connected = False
        print(f"[{self.name}] Disconnected")

    def _get(self, endpoint):
        if not self.connected: return None
        try:
            url = f"{self.host}{endpoint}"
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

    def _post(self, endpoint, payload):
        if not self.connected: return None
        try:
            url = f"{self.host}{endpoint}"
            headers = {'Content-Type': 'application/json'}
            requests.post(url, data=json.dumps(payload), headers=headers, timeout=1)
        except:
            pass

    # --- 기능 함수들 ---
    def get_pose(self):
        data = self._get("/api/core/slam/v1/localization/pose")
        if data:
            return data
        return None

    def get_laser_scan(self):
        return self._get("/api/core/slam/v1/lidar/scan")

    def get_map_explore(self):
        try:
            if not self.connected: return None
            url = f"{self.host}/api/core/slam/v1/maps/explore"
            response = requests.get(url, headers={'Accept': 'application/octet-stream'}, timeout=3)
            if response.status_code == 200:
                return response.content
        except:
            pass
        return None

    def get_pois(self):
        # POI는 로봇 내부 API가 없으면 빈 리스트 반환 (필요시 구현)
        return []

    def get_rectangle_areas(self, area_type):
        # 금지구역 등 가져오기
        return []

    def move_to(self, x, y):
        # 단순 이동 명령 예시 (Action 사용)
        payload = {
            "action_name": "slamtec.agent.actions.MoveToAction",
            "options": {
                "target": {"x": x, "y": y, "z": 0},
                "move_options": {"mode": 0}
            }
        }
        self._post("/api/core/motion/v1/actions", payload)

    def stop(self):
        # 이동 정지 (현재 동작 취소)
        self._delete("/api/core/motion/v1/actions") # DELETE 메소드 필요 시 추가