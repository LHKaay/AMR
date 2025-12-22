import struct
import numpy as np
import base64
import math
import time
import cv2  # OpenCV required for map editing/cropping
from rest_api import MSISRobot

class MSIS_AMR_Controller:
    """
    High-level controller for MSIS AMR.
    Handles map processing, file I/O, and complex movement logic.
    """
    def __init__(self, robot: MSISRobot):
        self.robot = robot
        self.current_map_grid = None
        self.map_meta = None
        self.path_history = [] # Stores visited coordinates
        self.map_objects = []

    # ---------------------------------------------------------
    # Map Processing Functions
    # ---------------------------------------------------------
    def create_map_from_data(self, map_data):
        """
        Parses raw binary map data into a Numpy grid.
        Corresponds to 'Map Generation Function'.
        """
        if not map_data or len(map_data) < 36:
            return None
        
        # Parsing logic from original utils.py
        ox, oy = struct.unpack("<ff", map_data[0:8])
        nx, ny = struct.unpack("<II", map_data[8:16])
        res = struct.unpack("<f", map_data[16:20])[0]
        grid_data = map_data[36:36 + (nx * ny)]
        
        # 0-100 probability to 0-255 grayscale
        grid = np.frombuffer(grid_data, dtype=np.uint8).reshape((ny, nx))
        
        self.current_map_grid = grid
        self.map_meta = {
            'min_x': ox, 'max_x': ox + nx*res, 
            'min_y': oy, 'max_y': oy + ny*res,
            'resolution': res,
            'origin_x': ox, 'origin_y': oy,
            'width': nx, 'height': ny
        }
        return grid, self.map_meta

    def crop_map(self, x1, y1, x2, y2):
        """
        Crops the current map grid based on physical coordinates.
        """
        if self.current_map_grid is None:
            print("No map data loaded.")
            return None
        
        meta = self.map_meta
        res = meta['resolution']
        ox, oy = meta['origin_x'], meta['origin_y']
        
        # Convert physical coords to pixel indices
        idx_x1 = int((x1 - ox) / res)
        idx_y1 = int((y1 - oy) / res)
        idx_x2 = int((x2 - ox) / res)
        idx_y2 = int((y2 - oy) / res)
        
        # Ensure indices are within bounds and ordered
        ix_min, ix_max = sorted([max(0, idx_x1), min(meta['width'], idx_x2)])
        iy_min, iy_max = sorted([max(0, idx_y1), min(meta['height'], idx_y2)])
        
        cropped_grid = self.current_map_grid[iy_min:iy_max, ix_min:ix_max]
        return cropped_grid

    def add_furniture(self, type, x, y, width, height=0.0):
        """
        가구(장애물) 정보를 리스트에 저장합니다.
        type: 'rect' (사각형 테이블/팔레트) 또는 'circle' (원형 테이블)
        x, y: 물리적 중심 좌표 (미터)
        width: 너비 (미터) 또는 지름
        height: 높이 (미터, 사각형일 경우만 사용)
        """
        self.map_objects.append({
            'type': type,
            'x': x, 'y': y,
            'w': width, 'h': height
        })
        print(f"Furniture added: {type} at ({x}, {y})")

    def save_map_as_svg(self, filename="map.svg", render_contour=True):
        """
        기본 지도(최적화된 SVG) 위에 가구 객체들을 그려서 저장합니다.
        Args:
            filename: 저장할 파일 경로
            render_contour: True일 경우 OpenCV를 이용해 벽의 윤곽선을 부드럽게 그립니다.
        """
        if self.current_map_grid is None: return False
        
        h, w = self.current_map_grid.shape
        # 상하 반전 (이미지 좌표계 대응: numpy 배열은 0행이 맨 위지만, 지도 데이터는 보통 0행이 y=0(아래))
        # 하지만 display 시에는 flipud를 하여 시각적으로 맞춥니다.
        grid = np.flipud(self.current_map_grid) 
        
        # 1. SVG 헤더 생성
        svg_parts = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">']
        svg_parts.append(f'<rect width="{w}" height="{h}" fill="#808080"/>') # 회색 배경 (미탐색 영역)

        # 2. 지도 데이터 그리기 (Run-Length Encoding 최적화 적용)
        # 픽셀 하나하나가 아니라, 연속된 색상을 하나의 rect로 병합하여 그립니다.
        for y in range(h):
            row = grid[y]
            current_color = None
            start_x = 0
            run_length = 0
            
            for x in range(w):
                val = row[x]
                # SLAMTEC 맵 데이터: 0(자유), 100(장애물), -1/128(미탐색)
                # 여기서는 127 이상을 장애물(검정), 0 초과를 자유(흰색)으로 처리
                if val > 127: pixel_color = "#000000" # 장애물
                elif val == 0: pixel_color = "#FFFFFF" # 이동 가능 구역 (0으로 가정)
                else: pixel_color = None # 그 외(미탐색 등)는 배경색 유지

                if pixel_color == current_color:
                    run_length += 1
                else:
                    if current_color is not None:
                        # 이전 구간 그리기
                        svg_parts.append(f'<rect x="{start_x}" y="{y}" width="{run_length}" height="1" fill="{current_color}"/>')
                    current_color = pixel_color
                    start_x = x
                    run_length = 1
            # 행의 마지막 구간 처리
            if current_color is not None:
                svg_parts.append(f'<rect x="{start_x}" y="{y}" width="{run_length}" height="1" fill="{current_color}"/>')

        # 3. [옵션] 컨투어(윤곽선) 렌더링 - 벽을 매끄러운 선으로 표현
        if render_contour:
            try:
                # 장애물 영역 마스킹 (0=이동가능, 127~255=장애물로 가정, 데이터 포맷에 따라 조정 필요)
                # 여기서는 '이동 가능 구역(흰색)'의 경계를 따거나 '장애물'의 경계를 땁니다.
                # 보통 이동 가능 구역(0)을 제외한 나머지를 벽으로 봅니다.
                mask = np.zeros((h, w), dtype=np.uint8)
                # grid > 100 인 곳을 벽으로 간주
                mask[grid > 100] = 255 
                
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                path_str = ""
                for cnt in contours:
                    epsilon = 0.002 * cv2.arcLength(cnt, True) 
                    approx = cv2.approxPolyDP(cnt, epsilon, True)
                    if len(approx) > 2:
                        pts = approx.reshape(-1, 2)
                        path_str += f"M {pts[0][0]} {pts[0][1]} "
                        for i in range(1, len(pts)):
                            path_str += f"L {pts[i][0]} {pts[i][1]} "
                        path_str += "Z "
                
                if path_str:
                    # 외곽선 스타일: 검정색 테두리
                    svg_parts.append(f'<path d="{path_str}" stroke="black" stroke-width="0.5" fill="none" shape-rendering="geometricPrecision"/>')
            except Exception as e:
                print(f"Contour rendering failed: {e}")

        # 4. 가구/장애물 객체 추가 (기존 로직 유지)
        meta = self.map_meta
        res = meta['resolution']
        ox, oy = meta['origin_x'], meta['origin_y']

        for obj in self.map_objects:
            idx_x = (obj['x'] - ox) / res
            idx_y = (obj['y'] - oy) / res
            
            # SVG y좌표 (grid가 flipud 되었으므로 h-1-idx_y 사용)
            svg_y = h - 1 - idx_y 
            svg_x = idx_x

            px_w = obj['w'] / res
            px_h = obj['h'] / res

            if obj['type'] == 'rect':
                rect_x = svg_x - (px_w / 2)
                rect_y = svg_y - (px_h / 2)
                svg_parts.append(
                    f'<rect x="{rect_x:.2f}" y="{rect_y:.2f}" width="{px_w:.2f}" height="{px_h:.2f}" '
                    f'fill="#8B4513" stroke="black" stroke-width="0.5" opacity="0.8" />'
                )
            elif obj['type'] == 'circle':
                radius = px_w / 2
                svg_parts.append(
                    f'<circle cx="{svg_x:.2f}" cy="{svg_y:.2f}" r="{radius:.2f}" '
                    f'fill="#FFFFFF" stroke="black" stroke-width="0.5" opacity="0.9" />'
                )

        # 5. Path(이동 경로) 그리기 - display_path_on_map 대신 SVG에 직접 추가
        if self.path_history:
            path_svg_points = []
            for (px, py) in self.path_history:
                 ix = (px - ox) / res
                 iy = (py - oy) / res
                 path_svg_points.append(f"{ix},{h - 1 - iy}")
            
            if len(path_svg_points) > 1:
                points_str = " ".join(path_svg_points)
                svg_parts.append(f'<polyline points="{points_str}" fill="none" stroke="red" stroke-width="1" opacity="0.7" />')

        # 6. 파일 저장
        svg_parts.append('</svg>')
        with open(filename, "w", encoding="utf-8") as f:
            f.write("".join(svg_parts))
        print(f"Optimized Map saved to {filename} (Contours: {render_contour})")
        return True

    def edit_map_add_obstacle(self, x, y, radius_pixels=5):
        """
        Edits the local map data to add a circular obstacle (Simulated Edit).
        Note: This edits the Numpy array, not the robot's internal SLAM map directly.
        """
        if self.current_map_grid is None: return
        
        meta = self.map_meta
        # Convert physical (x, y) to grid index
        idx_x = int((x - meta['origin_x']) / meta['resolution'])
        idx_y = int((y - meta['origin_y']) / meta['resolution'])
        
        # Use OpenCV to draw a circle on the grid
        cv2.circle(self.current_map_grid, (idx_x, idx_y), radius_pixels, (255), -1) # 255 in uint8 usually means obstacle or specific value depending on map standard
        print(f"Added local obstacle at ({x}, {y})")

    def add_custom_obstacle_to_robot(self, x1, y1, x2, y2):
        """
        Adds a Forbidden Area (Virtual Wall/Obstacle) to the actual robot.
        """
        return self.robot.add_rectangle_area("forbidden_area", [x1, y1], [x2, y2])

    # ---------------------------------------------------------
    # Movement Functions
    # ---------------------------------------------------------
    def move_to_target(self, x, y):
        """Moves robot to target coordinate."""
        print(f"Moving to ({x}, {y})...")
        self.record_path_point()
        return self.robot.move_to(x, y)

    def move_straight(self, distance_meters):
        """
        Moves the robot straight forward by a specific distance.
        Calculates target point based on current Yaw.
        """
        pose = self.robot.get_pose()
        if not pose: return
        
        curr_x, curr_y, curr_yaw = pose['x'], pose['y'], pose['yaw']
        
        # Calculate target based on yaw
        target_x = curr_x + distance_meters * math.cos(curr_yaw)
        target_y = curr_y + distance_meters * math.sin(curr_yaw)
        
        print(f"Moving straight {distance_meters}m to ({target_x:.2f}, {target_y:.2f})")
        return self.move_to_target(target_x, target_y)

    def move_rectangular_path(self, target_x, target_y):
        """
        Moves the robot using an orthogonal (rectangular) path.
        Logic: Current -> Intermediate (Corner) -> Target.
        Ensures 90-degree turns.
        """
        pose = self.robot.get_pose()
        if not pose: return

        start_x, start_y = pose['x'], pose['y']
        
        # Determine corner point (Option: Move X first, then Y)
        corner_x = target_x
        corner_y = start_y
        
        print(f"Executing Rectangular Move: ({start_x},{start_y}) -> ({corner_x},{corner_y}) -> ({target_x},{target_y})")
        
        # 1. Move to Corner
        self.move_to_target(corner_x, corner_y)
        self.wait_until_idle() # Blocking wait
        
        # 2. Move to Target
        self.move_to_target(target_x, target_y)
        self.wait_until_idle()

    def move_multi_point(self, points_list):
        """
        Moves through a list of coordinates sequentially.
        points_list: list of dicts [{'x': 1.0, 'y': 2.0}, ...]
        """
        print(f"Starting Multi-point Move: {len(points_list)} points")
        for i, pt in enumerate(points_list):
            print(f"Step {i+1}: Going to ({pt['x']}, {pt['y']})")
            self.move_to_target(pt['x'], pt['y'])
            self.wait_until_idle()
            time.sleep(0.5) # Short pause between points

    def wait_until_idle(self, timeout=30):
        """
        Blocks execution until the robot finishes moving.
        Checks status periodically.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Note: This checks if the robot is close to target or status is idle.
            # Simplified check using velocity or status API if available.
            # Here we check if 'actions' list is empty or use a simple sleep for demo.
            
            actions = self.robot.get_action_status()
            # If actions list is empty or None, robot is idle
            if not actions or len(actions) == 0:
                print(" > Movement finished.")
                return True
            
            # Additional check: distance to target (omitted for brevity)
            self.record_path_point()
            time.sleep(0.5)
        print(" > Wait Timeout.")
        return False

    def record_path_point(self):
        """Records current position for path visualization."""
        p = self.robot.get_pose()
        if p:
            self.path_history.append((p['x'], p['y']))

    def display_path_on_map(self):
        """
        Draws the recorded path on the current map grid (for SVG export or view).
        """
        if self.current_map_grid is None or not self.path_history: return
        
        meta = self.map_meta
        for (px, py) in self.path_history:
             idx_x = int((px - meta['origin_x']) / meta['resolution'])
             idx_y = int((py - meta['origin_y']) / meta['resolution'])
             
             # Draw small dot for path
             try:
                # 127 is usually gray, 0 is white/free, 255 is black/obstacle. 
                # Marking with distinct value if possible or editing grid.
                if 0 <= idx_x < meta['width'] and 0 <= idx_y < meta['height']:
                    self.current_map_grid[idx_y, idx_x] = 100 # Arbitrary value for path
             except: pass
        print(f"Path with {len(self.path_history)} points marked on map data.")