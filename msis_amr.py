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
        self.path_history = []  # Stores visited coordinates
        self.map_objects = []
        self.planned_path = []  # Path planned by user (clicks)
        
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
        
        # Convert 0-100 probability to 0-255 grayscale (uint8)
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
    
    # Coordinate Transformation Helpers
    def pixel_to_world(self, px, py):
        """Converts pixel coordinates (image x, y) to world coordinates (meters)."""
        if not self.map_meta: return 0, 0
        res = self.map_meta['resolution']
        ox = self.map_meta['origin_x']
        oy = self.map_meta['origin_y']
        h = self.map_meta['height']
        
        # Invert Y-axis: Image (Top-0) -> Map (Bottom-0)
        real_py = h - 1 - py 
        
        wx = (px * res) + ox
        wy = (real_py * res) + oy
        return wx, wy
    
    def world_to_pixel(self, wx, wy):
        """Converts world coordinates (meters) to pixel coordinates."""
        if not self.map_meta: return 0, 0
        res = self.map_meta['resolution']
        ox = self.map_meta['origin_x']
        oy = self.map_meta['origin_y']
        h = self.map_meta['height']
        
        px = int((wx - ox) / res)
        grid_y = int((wy - oy) / res)
        
        # Invert Y-axis: Map (Bottom-0) -> Image (Top-0)
        py = h - 1 - grid_y
        return px, py

    def get_map_image_with_overlays(self):
        """Returns the current map with robot position, path history, and planned path drawn (RGB Numpy Array)."""
        if self.current_map_grid is None: 
            return np.zeros((100, 100, 3), dtype=np.uint8)

        # 1. Convert Grayscale Grid to RGB
        # Flip vertically to match visual orientation (Image 0,0 is top-left)
        base_grid = np.flipud(self.current_map_grid)
        img_color = cv2.cvtColor(base_grid, cv2.COLOR_GRAY2RGB)
        
        # 2. Color Correction (Optional)
        # Unexplored(128) -> Gray, Obstacle(>128) -> Black, Free(0) -> White

        # 3. Draw Path History (Red Dots)
        for wx, wy in self.path_history:
            px, py = self.world_to_pixel(wx, wy)
            cv2.circle(img_color, (px, py), 2, (0, 0, 255), -1)

        # 4. Draw Planned Path (Blue Line and Dots)
        if len(self.planned_path) > 0:
            pts = []
            for wx, wy in self.planned_path:
                px, py = self.world_to_pixel(wx, wy)
                pts.append([px, py])
                cv2.circle(img_color, (px, py), 4, (255, 0, 0), -1) # Blue dot
            
            if len(pts) > 1:
                cv2.polylines(img_color, [np.array(pts)], False, (255, 0, 0), 2) # Blue line connection

        # 5. Draw Current Robot Position (Green Large Dot)
        pose = self.robot.get_pose()
        if pose:
            rx, ry = self.world_to_pixel(pose['x'], pose['y'])
            cv2.circle(img_color, (rx, ry), 6, (0, 255, 0), -1) 
            # Draw Orientation (Line)
            yaw = pose['yaw']
            end_x = int(rx + 15 * math.cos(yaw)) # Note: Sin sign might need check due to Y-axis inversion
            end_y = int(ry - 15 * math.sin(yaw)) 
            cv2.line(img_color, (rx, ry), (end_x, end_y), (0, 255, 0), 2)

        return img_color

    def move_smooth_path(self, points_list):
        """
        Moves through multiple points smoothly.
        Switches to the next command when within a radius of the current target.
        """
        print(f"Starting Smooth Path: {len(points_list)} waypoints")
        switching_radius = 0.5  # Distance (meters) to switch to next waypoint

        for i, pt in enumerate(points_list):
            is_last_point = (i == len(points_list) - 1)
            target_x, target_y = pt['x'], pt['y']
            
            print(f" >> Moving to Waypoint {i+1}: ({target_x:.2f}, {target_y:.2f})")
            self.robot.move_to(target_x, target_y)
            
            # Monitoring Loop
            while True:
                pose = self.robot.get_pose()
                if not pose: 
                    time.sleep(0.1)
                    continue

                self.record_path_point() # Record Path
                
                # Calculate Distance
                dist = math.hypot(pose['x'] - target_x, pose['y'] - target_y)

                # Wait until idle if it is the last point
                if is_last_point:
                    actions = self.robot.get_action_status()
                    if not actions or len(actions) == 0:
                        print(" >> Final Destination Reached.")
                        break
                
                # If intermediate point, switch when close enough
                else:
                    if dist < switching_radius:
                        print(f" >> Within {dist:.2f}m. Switching to next point...")
                        break 
                
                time.sleep(0.2)
        return True

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
        Adds furniture (obstacle) info to the list.
        type: 'rect' or 'circle'
        """
        self.map_objects.append({
            'type': type,
            'x': x, 'y': y,
            'w': width, 'h': height
        })
        print(f"Furniture added: {type} at ({x}, {y})")

    def save_map_as_svg(self, filename="map.svg", render_contour=True):
        """
        Saves the map as an optimized SVG with optional contours.
        """
        if self.current_map_grid is None: return False
        
        h, w = self.current_map_grid.shape
        # Flip UD for visual alignment
        grid = np.flipud(self.current_map_grid) 
        
        # 1. Create SVG Header
        svg_parts = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">']
        svg_parts.append(f'<rect width="{w}" height="{h}" fill="#808080"/>') # Gray Background

        # 2. Draw Map Data (RLE Optimization)
        for y in range(h):
            row = grid[y]
            current_color = None
            start_x = 0
            run_length = 0
            
            for x in range(w):
                val = row[x]
                if val > 127: pixel_color = "#000000" # Obstacle
                elif val == 0: pixel_color = "#FFFFFF" # Free Space
                else: pixel_color = None 

                if pixel_color == current_color:
                    run_length += 1
                else:
                    if current_color is not None:
                        svg_parts.append(f'<rect x="{start_x}" y="{y}" width="{run_length}" height="1" fill="{current_color}"/>')
                    current_color = pixel_color
                    start_x = x
                    run_length = 1
            if current_color is not None:
                svg_parts.append(f'<rect x="{start_x}" y="{y}" width="{run_length}" height="1" fill="{current_color}"/>')

        # 3. Contour Rendering
        if render_contour:
            try:
                mask = np.zeros((h, w), dtype=np.uint8)
                mask[grid > 100] = 255 # Mask obstacles
                
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
                    svg_parts.append(f'<path d="{path_str}" stroke="black" stroke-width="0.5" fill="none" shape-rendering="geometricPrecision"/>')
            except Exception as e:
                print(f"Contour rendering failed: {e}")

        # 4. Add Furniture Objects
        meta = self.map_meta
        res = meta['resolution']
        ox, oy = meta['origin_x'], meta['origin_y']

        for obj in self.map_objects:
            idx_x = (obj['x'] - ox) / res
            idx_y = (obj['y'] - oy) / res
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

        # 5. Draw Path History
        if self.path_history:
            path_svg_points = []
            for (px, py) in self.path_history:
                 ix = (px - ox) / res
                 iy = (py - oy) / res
                 path_svg_points.append(f"{ix},{h - 1 - iy}")
            
            if len(path_svg_points) > 1:
                points_str = " ".join(path_svg_points)
                svg_parts.append(f'<polyline points="{points_str}" fill="none" stroke="red" stroke-width="1" opacity="0.7" />')

        # 6. Write File
        svg_parts.append('</svg>')
        with open(filename, "w", encoding="utf-8") as f:
            f.write("".join(svg_parts))
        print(f"Optimized Map saved to {filename} (Contours: {render_contour})")
        return True

    def edit_map_add_obstacle(self, x, y, radius_pixels=5):
        """
        Edits the local map data to add a circular obstacle (Simulated Edit).
        """
        if self.current_map_grid is None: return
        
        meta = self.map_meta
        idx_x = int((x - meta['origin_x']) / meta['resolution'])
        idx_y = int((y - meta['origin_y']) / meta['resolution'])
        
        cv2.circle(self.current_map_grid, (idx_x, idx_y), radius_pixels, (255), -1) 
        print(f"Added local obstacle at ({x}, {y})")

    def add_custom_obstacle_to_robot(self, x1, y1, x2, y2):
        """Adds a Forbidden Area to the actual robot."""
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
        """Moves the robot straight forward by a specific distance."""
        pose = self.robot.get_pose()
        if not pose: return
        
        curr_x, curr_y, curr_yaw = pose['x'], pose['y'], pose['yaw']
        
        target_x = curr_x + distance_meters * math.cos(curr_yaw)
        target_y = curr_y + distance_meters * math.sin(curr_yaw)
        
        print(f"Moving straight {distance_meters}m to ({target_x:.2f}, {target_y:.2f})")
        return self.move_to_target(target_x, target_y)

    def move_rectangular_path(self, target_x, target_y):
        """Moves the robot using an orthogonal (rectangular) path."""
        pose = self.robot.get_pose()
        if not pose: return

        start_x, start_y = pose['x'], pose['y']
        
        corner_x = target_x
        corner_y = start_y
        
        print(f"Executing Rectangular Move: ({start_x},{start_y}) -> ({corner_x},{corner_y}) -> ({target_x},{target_y})")
        
        self.move_to_target(corner_x, corner_y)
        self.wait_until_idle() 
        
        self.move_to_target(target_x, target_y)
        self.wait_until_idle()

    def move_multi_point(self, points_list):
        """Moves through a list of coordinates sequentially."""
        print(f"Starting Multi-point Move: {len(points_list)} points")
        for i, pt in enumerate(points_list):
            print(f"Step {i+1}: Going to ({pt['x']}, {pt['y']})")
            self.move_to_target(pt['x'], pt['y'])
            self.wait_until_idle()
            time.sleep(0.5) 

    def wait_until_idle(self, timeout=30):
        """Blocks execution until the robot finishes moving."""
        start_time = time.time()
        while time.time() - start_time < timeout: 
            actions = self.robot.get_action_status()
            if not actions or len(actions) == 0:
                print(" > Movement finished.")
                return True
            
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
        """Draws the recorded path on the current map grid."""
        if self.current_map_grid is None or not self.path_history: return
        
        meta = self.map_meta
        for (px, py) in self.path_history:
             idx_x = int((px - meta['origin_x']) / meta['resolution'])
             idx_y = int((py - meta['origin_y']) / meta['resolution'])
             
             if 0 <= idx_x < meta['width'] and 0 <= idx_y < meta['height']:
                    self.current_map_grid[idx_y, idx_x] = 100 
        print(f"Path with {len(self.path_history)} points marked on map data.")