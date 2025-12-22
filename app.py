import struct
import numpy as np
import json
import gradio as gr
import folium
from branca.element import MacroElement
from jinja2 import Template
import base64
import math
import os
import requests

# [중요] api.py에서 manager 임포트
try:
    from api import manager
except ImportError:
    print("❌ 오류: 'api.py' 파일을 찾을 수 없습니다.")
    exit()

# try:
#     from data_logger import recorder  # <--- 새로 만든 모듈 임포트
# except ImportError:
#     print("❌ 'data_logger.py'가 없습니다. 녹화 기능이 작동하지 않습니다.")
#     recorder = None

# --------------------------
# 1. 데이터 파싱 & SVG 생성 (조건부 외곽선)
# --------------------------
def parse_grid_and_meta(content):
    if not content or len(content) < 36: return None, None
    ox, oy = struct.unpack("<ff", content[0:8])
    nx, ny = struct.unpack("<II", content[8:16])
    res = struct.unpack("<f", content[16:20])[0]
    grid_data = content[36:36 + (nx * ny)]
    grid = np.frombuffer(grid_data, dtype=np.uint8).reshape((ny, nx))
    meta = {'min_x': ox, 'max_x': ox + nx*res, 'min_y': oy, 'max_y': oy + ny*res}
    return grid, meta

def generate_map_base64(grid, render_contour=False):
    h, w = grid.shape
    grid = np.flipud(grid)
    
    svg_parts = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">']
    svg_parts.append(f'<rect width="{w}" height="{h}" fill="#808080"/>')

    for y in range(h):
        row = grid[y]
        current_color = None
        start_x = 0
        run_length = 0
        for x in range(w):
            val = row[x]
            if val > 127: pixel_color = "#000000"
            elif val > 0: pixel_color = "#FFFFFF"
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

    if render_contour:
        try:
            import cv2
            mask = np.zeros((h, w), dtype=np.uint8)
            mask[(grid > 0) & (grid <= 127)] = 255
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
        except ImportError: pass
        except Exception as e: print(f"Contour Error: {e}")

    svg_parts.append('</svg>')
    svg_str = "".join(svg_parts)
    return f"data:image/svg+xml;base64,{base64.b64encode(svg_str.encode('utf-8')).decode()}"

def get_logo_html(image_path):
    if not os.path.exists(image_path):
        return f"<div style='color:red;'>⚠️ Logo not found: {image_path}</div>"
    with open(image_path, "rb") as img_file:
        img_b64 = base64.b64encode(img_file.read()).decode('utf-8')
    return f"""<div style="display: flex; justify-content: center; margin-bottom: 10px;"><img src="data:image/png;base64,{img_b64}" alt="Logo" style="width: 100%; object-fit: contain;"></div>"""

# --------------------------
# 2. 지도 관리 JS
# --------------------------
class MSISManager(MacroElement):
    _template = Template("""
        {% macro script(this, kwargs) %}
        var map = {{ this._parent.get_name() }};
        
        // --- Layer Groups ---
        var mapLayer = L.layerGroup().addTo(map);    // 지도 이미지
        var areaLayer = L.layerGroup().addTo(map);   // 금지 구역
        var poiLayer = L.layerGroup().addTo(map);    // POI
        var robotLayer = L.layerGroup().addTo(map);  // 로봇 본체
        var lidarLayer = L.layerGroup().addTo(map);  // 라이다 (점 + 폴리곤)
        var axisLayer = L.layerGroup().addTo(map); // Axis 레이어
        
        // Axis 그리기 (초기 1회)
        L.circleMarker([0,0], {radius: 4, color: '#0000FF', fillOpacity: 1, interactive: false}).addTo(axisLayer);
        L.polyline([[0,0], [1, 0]], {color: '#FF0000', weight: 4, interactive: false}).addTo(axisLayer); // X축
        L.polyline([[0,0], [0, 1]], {color: '#00FF00', weight: 4, interactive: false}).addTo(axisLayer); // Y축
         
        // --- LiDAR Components ---
        // 폴리곤(스캔 영역)은 점들과 동기화되어야 하므로 같은 레이어 그룹 사용
        var scanPolygon = L.polygon([], {
            color: '#FF3366', weight: 0, fillOpacity: 0.2, fillColor: '#FF3366', interactive: false
        }); 
        
        // ----------------------------------------------------
        // 1. Robot Pose Update (위치 정보)
        // ----------------------------------------------------
        function updatePose() {
            try {
                var ta = window.parent.document.querySelector('#json_pose textarea');
                if (!ta || !ta.value) return;
                var data = JSON.parse(ta.value);

                // [수정] 레이어 Show/Hide 처리
                if (data.visible) {
                    if (!map.hasLayer(robotLayer)) map.addLayer(robotLayer);
                } else {
                    if (map.hasLayer(robotLayer)) map.removeLayer(robotLayer);
                }
                         
                // 로봇이 보여야 할 때만 그리기 연산 수행
                if (data.visible) {
                    robotLayer.clearLayers();
                    if (data.multi_poses) {
                        data.multi_poses.forEach(function(r) {
                            var shapes = drawRobot(r.x, r.y, r.yaw, r.name, r.is_selected, r.has_error);
                            shapes.forEach(s => s.addTo(robotLayer));
                        });
                    }
                }
            } catch(e) {}
        }

        // ----------------------------------------------------
        // 2. LiDAR Update (점 + 폴리곤 동기화)
        // ----------------------------------------------------
        function updateLidar() {
            try {
                var ta = window.parent.document.querySelector('#json_lidar textarea');
                if (!ta || !ta.value) return;
                var data = JSON.parse(ta.value);
                
                // [수정] 레이어 Show/Hide 처리
                if (data.visible) {
                    if (!map.hasLayer(lidarLayer)) map.addLayer(lidarLayer);
                } else {
                    if (map.hasLayer(lidarLayer)) map.removeLayer(lidarLayer);
                }
                
                // 데이터가 있고, 로봇 위치가 있어야 그릴 수 있음
                if (data.visible && data.scan && data.pose) {
                    lidarLayer.clearLayers();
                    var rx = data.pose.x, ry = data.pose.y, ryaw = data.pose.yaw;
                    var points = data.scan.laser_points;
                    
                    // [중요] 폴리곤용 좌표 배열 (로봇 중심에서 시작)
                    var polyCoords = [[ry, rx]]; 
                    
                    // 거리 필터링 및 각도 정렬 (필요시)
                    var validPoints = points.filter(p => p.distance > 0.05);

                    validPoints.forEach((p, i) => {
                        var ga = p.angle + ryaw; // 글로벌 각도 계산
                        var wy = ry + p.distance * Math.sin(ga);
                        var wx = rx + p.distance * Math.cos(ga);
                        var coord = [wy, wx];

                        // 1. 폴리곤 좌표에 추가
                        polyCoords.push(coord);

                        // 2. 점(Point) 그리기 (성능을 위해 3개당 1개만 그리기 등 최적화 가능)
                        if (i % 2 === 0) { 
                            L.circleMarker(coord, {
                                radius: 1, color: '#FF0000', fillOpacity: 0.8, stroke: false, interactive: false
                            }).addTo(lidarLayer);
                        }
                    });

                    // 폴리곤 닫기 (다시 로봇 중심으로)
                    polyCoords.push([ry, rx]);
                    
                    // 3. 폴리곤 업데이트 및 레이어 추가
                    scanPolygon.setLatLngs(polyCoords);
                    scanPolygon.addTo(lidarLayer);
                }
            } catch(e) {}
        }

        // ----------------------------------------------------
        // 3. Map & Static Update (지도, 구역, POI)
        // ----------------------------------------------------
        function updateMapStatic() {
            try {
                var ta = window.parent.document.querySelector('#json_map textarea');
                if (!ta || !ta.value) return;
                // 내용이 바뀌었을 때만 파싱하도록 로직 추가 가능
                var data = JSON.parse(ta.value);

                // 지도 이미지 (URL이 바뀌었을 때만 갱신 권장)
                if (data.map_url) {
                    if (!map.hasLayer(mapLayer)) {
                        L.imageOverlay(data.map_url, data.bounds, {zIndex: 1}).addTo(mapLayer);
                        map.fitBounds(data.bounds); // 처음 로드 시 핏
                    }
                }

                // 금지 구역
                areaLayer.clearLayers();
                if (data.areas) {
                    data.areas.forEach(area => {
                        var p1 = [area.area.start.y, area.area.start.x];
                        var p2 = [area.area.end.y, area.area.end.x];
                        L.rectangle([p1, p2], {color: "#000000", weight: 1, fillColor: "#000000", fillOpacity: 0.3})
                         .addTo(areaLayer);
                    });
                }
                
                // POI
                poiLayer.clearLayers();
                if (data.pois) {
                    data.pois.forEach(p => {
                         L.circleMarker([p.y, p.x], { radius: 5, color: '#2196F3' }).addTo(poiLayer);
                    });
                }

            } catch(e) {}
        }
        
        // 헬퍼 함수들 (getBezierPoints, drawRobot 등은 기존 유지)
        function drawRobot(x, y, yaw, name, isSelected, hasError) {

            var bodyColor = isSelected ? '#2196F3' : '#9E9E9E'; 
             if (hasError) bodyColor = '#000000';
             var l = 0.74, w = 0.44; 
             var corners = [[l/2, w/2], [l/2, -w/2], [-l/2, -w/2], [-l/2, w/2]].map(p => [
                y + (p[0]*Math.sin(yaw) + p[1]*Math.cos(yaw)), 
                x + (p[0]*Math.cos(yaw) - p[1]*Math.sin(yaw))
             ]);
             var poly = L.polygon(corners, {color: bodyColor, weight: 2, fillOpacity: 0.8, interactive: true});
             poly.bindTooltip(name + (isSelected ? " (ME)" : ""), {permanent: false, direction: "top", offset: [0, -10]});
             var arrowCorners = [[0.18, 0], [-0.18, 0.13], [-0.18, -0.13]].map(p => [
                y + (p[0]*Math.sin(yaw) + p[1]*Math.cos(yaw)), 
                x + (p[0]*Math.cos(yaw) - p[1]*Math.sin(yaw))
             ]);
             return [poly, L.polygon(arrowCorners, {color: '#FF0000', weight: 1, fillOpacity: 1, fillColor: '#FF0000', interactive: false})];
        }

        setInterval(updatePose, 100);
        setInterval(updateLidar, 200);
        setInterval(updateMapStatic, 1000);
        {% endmacro %}
    """)

# --------------------------
# 3. 백엔드 함수
# --------------------------
def get_map_view(robot_name=None, render_contour=False):
    if not robot_name:
        all_robots = manager.get_all_robots()
        if not all_robots:
            return "<div style='color:white;text-align:center;margin-top:20px;'><h3>No Robots Added</h3></div>"
        target_robot = list(all_robots.values())[0]
    else:
        target_robot = manager.get_robot(robot_name)

    content = target_robot.get_map_explore()
    if not content: return "<div style='color:white;text-align:center;margin-top:20px;'><h3>Map Offline</h3></div>"
    
    grid, meta = parse_grid_and_meta(content)
    img_b64 = generate_map_base64(grid, render_contour=render_contour)
    bounds = [[meta['min_y'], meta['min_x']], [meta['max_y'], meta['max_x']]]
    
    m = folium.Map(crs="Simple", tiles=None, zoom_control=False, attribution_control=False)
    m.get_root().header.add_child(folium.Element("<style>html, body, #map, .leaflet-container { background-color: #808080 !important; margin:0; padding:0; height:100%; width:100%; overflow: hidden; } .leaflet-image-layer { image-rendering: pixelated; } .robot-label { background: rgba(0,0,0,0.7); border: none; box-shadow: none; color: white; font-weight: bold; padding: 2px 5px; border-radius: 4px; }</style>"))
    m.get_root().html.add_child(folium.Element(f"<script>window.mapBounds = {bounds}; window.mapData = {{ url: '{img_b64}', bounds: {bounds} }};</script>"))
    m.add_child(MSISManager())
    return m._repr_html_()

# UI 업데이트 함수 (분리된 리턴값)
def update_ui_layers(selected_robot_name, show_map, show_laser, show_robot, show_axis):
    # 1. 기본 데이터 조회
    all_robots = manager.get_all_robots()
    target_robot = all_robots.get(selected_robot_name)
    
    if not target_robot:
        return "{}", "{}", "{}", "Wait...", "Wait..."

    # 2. 데이터 수집
    # (A) Pose & Robot Layer
    pose = target_robot.get_pose()
    multi_poses = []
    # ... (멀티 포즈 수집 로직 유지) ...
    for name, r in all_robots.items():
        p = r.get_pose()
        # ...
        if p:
            multi_poses.append({"name": name, "x": p["x"], "y": p["y"], "yaw": p["yaw"], "is_selected": (name == selected_robot_name), "has_error": False})

    # [수정] show_robot 플래그 추가
    json_pose = json.dumps({"multi_poses": multi_poses, "visible": show_robot})

    # (B) LiDAR Layer
    # [수정] show_laser 플래그 추가 (False면 무거운 스캔 데이터 안 가져오게 최적화 가능)
    scan = None
    if show_laser:
        scan = target_robot.get_laser_scan()
    json_lidar = json.dumps({"scan": scan, "pose": pose, "visible": show_laser}) 

    # (C) Map Layer
    # [수정] show_map, show_axis 플래그 추가
    pois = target_robot.get_pois()
    areas = target_robot.get_rectangle_areas("forbidden_area")
    
    json_map = json.dumps({
        "pois": pois, 
        "areas": areas, 
        "visible_map": show_map, 
        "visible_axis": show_axis,
        # 맵 URL은 필요시 여기에 포함 (혹은 JS 전역 변수 활용)
    })

    pose_str = f"📍 {selected_robot_name}: {pose['x']:.2f}, {pose['y']:.2f}" if pose else "No Pose"
    status_str = f"Connected: {len(all_robots)}"

    return json_pose, json_lidar, json_map, pose_str, status_str

# --- 로직 함수들 ---
def add_new_robot(name, ip):
    if not name or not ip: return gr.update(), "Enter Name & IP"
    new_list = manager.add_robot(name, ip)
    return gr.update(choices=new_list, value=name), f"Added {name}"

def remove_robot(name):
    if not name: return gr.update(), "Select Robot"
    new_list = manager.delete_robot(name)
    val = new_list[0] if new_list else None
    return gr.update(choices=new_list, value=val), f"Removed {name}"

def manual_move(robot_name, code):
    r = manager.get_robot(robot_name)
    if r: 
        payload = { "action_name": "slamtec.agent.actions.MoveByAction", "options": { "direction": code, "duration": 500 } }
        r._post("/api/core/motion/v1/actions", payload)

def cmd_stop(robot_name):
    r = manager.get_robot(robot_name)
    if r: r.stop()

def cmd_go_target(robot_name, json_str):
    r = manager.get_robot(robot_name)
    if r and json_str:
        c = json.loads(json_str)
        r.move_to(c['x'], c['y'])

def cmd_add_area(robot_name, x1, y1, x2, y2):
    r = manager.get_robot(robot_name)
    if r: 
        r.add_rectangle_area("forbidden_area", [x1, y1], [x2, y2])
        return f"Added Area: ({x1},{y1})~({x2},{y2})"
    return "Error: Robot not found"

def on_map_click(json_str, zoom_state):
    if not json_str: return "Target: None", zoom_state
    try:
        coords = json.loads(json_str)
        if zoom_state.get('is_selecting'):
            zoom_state['points'].append(coords)
            return f"Selecting... {len(zoom_state['points'])} points", zoom_state
        return f"Selected: X={coords['x']:.2f}, Y={coords['y']:.2f}", zoom_state
    except: return "Target: Error", zoom_state

# --- Zoom Logic ---
def toggle_zoom_selection(zoom_state):
    if zoom_state.get('is_selecting'):
        zoom_state['is_selecting'] = False
        return "✏️ Start Selection", zoom_state
    else:
        zoom_state['is_selecting'] = True
        return "⏹ Stop Selection", zoom_state

def apply_crop_zoom(zoom_state):
    points = zoom_state.get('points', [])
    if len(points) < 3:
        return zoom_state, ""
    
    zoom_state['is_cropped'] = True
    zoom_state['is_selecting'] = False
    
    xs = [p['x'] for p in points]
    ys = [p['y'] for p in points]
    pad = 0.5
    bounds = [[min(ys) - pad, min(xs) - pad], [max(ys) + pad, max(xs) + pad]]
    
    return "✏️ Start Selection", zoom_state, json.dumps({"bounds": bounds})

def reset_view_logic():
    new_state = {'is_selecting': False, 'is_cropped': False, 'points': []}
    return "✏️ Start Selection", new_state, json.dumps({"reset": True})

def refresh_map_view(robot_name, zoom_state):
    is_cropped = zoom_state.get('is_cropped', False) if zoom_state else False
    return get_map_view(robot_name, render_contour=is_cropped)

# --------------------------
# 4. GUI 구성 (Safe CSS)
# --------------------------

custom_css = """
/* 1. 기본 컨테이너 여백 제거 (안전한 방식) */
.gradio-container { 
    max-width: 100% !important; 
    padding: 0 !important; 
    margin: 0 !important; 
    background-color: #808080 !important;
}
body { 
    margin: 0; 
    padding: 0; 
    background-color: #808080 !important;
}
footer { display: none !important; }

/* 2. 메뉴바 (회색 + 흰색 글씨) */
#top_menu { 
    background-color: #808080 !important; 
    color: #FFFFFF !important; 
    padding: 10px 25px; 
    border-bottom: none 
}
.menu_btn { 
    background: none !important; 
    border: none !important; 
    color: #FFFFFF !important; 
    font-weight: 700 !important; 
    box-shadow: none !important; 
    cursor: pointer; 
    font-size: 16px !important;
}
.menu_btn:hover { color: #4CAF50 !important; }

/* 3. 사이드바 스타일 (흰색 배경) */
#sidebar { 
    background-color: #ffffff !important; 
    border-right: 1px solid #dcdcdc !important; 
    padding: 20px !important; 
    box-shadow: 2px 0 10px rgba(0,0,0,0.1); 
}

/* 4. 공통 컴포넌트 */
.section-header { 
    color: #2c3e50; 
    border-bottom: 2px solid #2196F3; 
    padding-bottom: 5px; 
    margin-top: 20px; 
    margin-bottom: 10px; 
    font-size: 16px; 
    font-weight: bold; 
}
button { border-radius: 6px !important; font-weight: 600 !important; transition: all 0.2s; }
.btn-nav { background-color: #f5f5f5 !important; color: #333 !important; border: 1px solid #ddd !important; font-size: 20px !important; height: 50px !important; }
.btn-nav:hover { background-color: #4CAF50 !important; color: white !important; border-color: #4CAF50 !important; }
.btn-stop { background-color: #212121 !important; color: white !important; border: 1px solid #000 !important; }
.btn-stop:hover { background-color: #424242 !important; }
.btn-primary-custom { background-color: #2196F3 !important; color: white !important; border: none !important; }
.btn-primary-custom:hover { background-color: #1976D2 !important; }
.btn-delete { background-color: #607D8B !important; color: white !important; }
input, textarea, select { background-color: #ffffff !important; border: 1px solid #ccc !important; color: #333 !important; }
.gradio-container label { color: #333 !important; }
.dpad-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; width: 180px; margin: 10px auto; }
.hidden-elem { display: none !important; }
iframe { height: 93vh !important; width: 100% !important; border: none !important; background-color: #808080 !important; }
"""

js_loader = """function() { console.log("UI Loaded"); }"""

robot_names = list(manager.get_all_robots().keys())
init_val = robot_names[0] if robot_names else None

with gr.Blocks(title="MSIS Control Studio") as demo:
    zoom_state = gr.State({'is_selecting': False, 'is_cropped': False, 'points': []})

    with gr.Row(elem_id="top_menu"):
        gr.Button("Motion", elem_classes="menu_btn")
        gr.Button("MAP", elem_classes="menu_btn").click(
            None, None, None, 
            js="(e) => { document.getElementById('zoom_section').scrollIntoView({behavior: 'smooth', block: 'start'}); }"
        )
        gr.Button("ARM", elem_classes="menu_btn")
        gr.Button("CAMERA", elem_classes="menu_btn")

    with gr.Row():
        # [복구] 안전한 사이드바 레이아웃
        with gr.Sidebar(elem_id="sidebar", width=350):
            logo_path = "MSIS_WB_logo.png"
            gr.HTML(get_logo_html(logo_path))

            gr.Markdown("## 🤖 MSIS Manager", elem_classes=["section-header"])
            robot_dropdown = gr.Dropdown(choices=robot_names, value=init_val, label="Select Target Robot", interactive=True)
            
            with gr.Accordion("➕ Add / Remove Robot", open=False):
                with gr.Row():
                    txt_name = gr.Textbox(label="Name", placeholder="AMR_01")
                    txt_ip = gr.Textbox(label="IP", placeholder="192.168.0.x")
                with gr.Row():
                    btn_add_robot = gr.Button("Add Robot", elem_classes=["btn-primary-custom"])
                    btn_del_robot = gr.Button("Delete Selected", elem_classes=["btn-delete"])
                msg_box = gr.Markdown("", elem_id="msg-box")

            with gr.Row():
                status_display = gr.Markdown("🔋 Status: Checking...")

            #     # === [UI 추가] 데이터 녹화 섹션 ===
            # gr.Markdown("💾 Data Recording", elem_classes=["section-header"])
            # with gr.Row():
            #     btn_record = gr.Button("🔴 REC (10s)", variant="stop")
            #     lbl_record_status = gr.Textbox(label="Status", value="Ready", interactive=False)
            # # =================================
            
            gr.Markdown("🎮 Manual Control", elem_classes=["section-header"])
            with gr.Column(elem_classes="dpad-grid"):
                gr.HTML("<div></div>")
                btn_up = gr.Button("▲", elem_classes=["btn-nav"])
                gr.HTML("<div></div>")
                btn_left = gr.Button("◀", elem_classes=["btn-nav"])
                btn_stop = gr.Button("STOP", elem_classes=["btn-stop"])
                btn_right = gr.Button("▶", elem_classes=["btn-nav"])
                gr.HTML("<div></div>")
                btn_down = gr.Button("▼", elem_classes=["btn-nav"])
                gr.HTML("<div></div>")

            gr.Markdown("📍 Navigation", elem_classes=["section-header"])
            pose_display = gr.Markdown("Position: ...")
            target_coords_json = gr.Textbox(elem_classes=["hidden-elem"], elem_id="target_coords_json")
            target_display = gr.Textbox(label="Target Info", value="No target clicked", interactive=False)
            btn_go_target = gr.Button("GO TO CLICKED TARGET", elem_classes=["btn-primary-custom"])

            gr.Markdown("🔍 Area Zoom & Crop", elem_classes=["section-header"], elem_id="zoom_section")
            zoom_cmd_json = gr.Textbox(elem_classes=["hidden-elem"], elem_id="zoom_cmd_json")
            
            with gr.Row():
                btn_toggle_select = gr.Button("✏️ Start Selection", variant="secondary")
            with gr.Row():
                btn_apply_crop = gr.Button("✅ Apply Crop", elem_classes=["btn-primary-custom"])
                btn_reset_view = gr.Button("🔄 Reset View", variant="secondary")

            gr.Markdown("🚫 Forbidden Area", elem_classes=["section-header"])
            gr.Markdown("**Start (X1, Y1)**")
            with gr.Row():
                in_x1 = gr.Number(label="X1", value=0.0, show_label=False, scale=1)
                in_y1 = gr.Number(label="Y1", value=0.0, show_label=False, scale=1)
            
            gr.Markdown("**End (X2, Y2)**")
            with gr.Row():
                in_x2 = gr.Number(label="X2", value=1.0, show_label=False, scale=1)
                in_y2 = gr.Number(label="Y2", value=1.0, show_label=False, scale=1)
            
            btn_area = gr.Button("Add Forbidden Area", elem_classes=["btn-primary-custom"])

            gr.Markdown("👁️ Layers", elem_classes=["section-header"])
            with gr.Row():
                chk_map = gr.Checkbox(label="Map", value=True)
                chk_laser = gr.Checkbox(label="Laser", value=True)
            with gr.Row():
                chk_robot = gr.Checkbox(label="Robot", value=True)
                chk_axis = gr.Checkbox(label="Axis", value=False)

        with gr.Column(elem_id="map-container"):
            map_html = gr.HTML(value=get_map_view(init_val))
            json_pose = gr.Textbox(elem_id="json_pose", visible=False)
            json_lidar = gr.Textbox(elem_id="json_lidar", visible=False)
            json_map = gr.Textbox(elem_id="json_map", visible=False)

    # --- Events ---
    btn_add_robot.click(add_new_robot, [txt_name, txt_ip], [robot_dropdown, msg_box])
    btn_del_robot.click(remove_robot, [robot_dropdown], [robot_dropdown, msg_box])

    robot_dropdown.change(refresh_map_view, [robot_dropdown, zoom_state], [map_html])

    btn_up.click(lambda r: manual_move(r, 0), [robot_dropdown], None)
    btn_down.click(lambda r: manual_move(r, 1), [robot_dropdown], None)
    btn_left.click(lambda r: manual_move(r, 3), [robot_dropdown], None)
    btn_right.click(lambda r: manual_move(r, 2), [robot_dropdown], None)
    btn_stop.click(cmd_stop, [robot_dropdown], None)
    
    target_coords_json.change(on_map_click, inputs=[target_coords_json, zoom_state], outputs=[target_display, zoom_state])
    btn_go_target.click(cmd_go_target, [robot_dropdown, target_coords_json], None)
    
    btn_area.click(cmd_add_area, [robot_dropdown, in_x1, in_y1, in_x2, in_y2], [msg_box])

    btn_toggle_select.click(toggle_zoom_selection, [zoom_state], [btn_toggle_select, zoom_state])
    
    btn_apply_crop.click(apply_crop_zoom, [zoom_state], [btn_toggle_select, zoom_state, zoom_cmd_json]) \
                  .then(refresh_map_view, [robot_dropdown, zoom_state], [map_html])

    btn_reset_view.click(reset_view_logic, None, [btn_toggle_select, zoom_state, zoom_cmd_json]) \
                  .then(refresh_map_view, [robot_dropdown, zoom_state], [map_html])

    timer = gr.Timer(value=0.2)
    timer.tick(
        update_ui_layers, 
        inputs=[robot_dropdown, chk_map, chk_laser, chk_robot, chk_axis], 
        outputs=[json_pose, json_lidar, json_map, pose_display, status_display]
    )
    demo.load(None, None, None, js=js_loader)

if __name__ == "__main__":
    demo.launch(css=custom_css)