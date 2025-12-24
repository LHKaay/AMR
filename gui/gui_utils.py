# gui_utils.py
import numpy as np
import base64
import struct
import json
import os
import time
import threading 
import csv
import folium
from branca.element import MacroElement
from jinja2 import Template

# api.py에서 manager import
try:
    from gui.rest_api import manager
except ImportError:
    print("Warning: rest_api.py not found. Using dummy manager.")
    class Dummy: pass
    manager = Dummy() # handle exception

# --------------------------
# 1. Map Data & Image Processing
# --------------------------
def parse_grid_and_meta(content):
    if not content or len(content) < 36: return None, None
    ox, oy = struct.unpack("<ff", content[0:8])
    nx, ny = struct.unpack("<II", content[8:16])
    res = struct.unpack("<f", content[16:20])[0]
    grid_data = content[36:36 + (nx * ny)]
    grid = np.frombuffer(grid_data, dtype=np.uint8).reshape((ny, nx))
    meta = {'min_x': ox, 'max_x': ox + nx*res, 'min_y': oy, 'max_y': oy + ny*res,
            'width': nx, 'height': ny, 'resolution': res}
    return grid, meta

def generate_map_base64(grid):
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

    svg_parts.append('</svg>')
    svg_str = "".join(svg_parts)
    return f"data:image/svg+xml;base64,{base64.b64encode(svg_str.encode('utf-8')).decode()}"

def get_logo_html(image_path):
    if not os.path.exists(image_path):
        return f"<div style='height:10px;'></div>"
    with open(image_path, "rb") as img_file:
        img_b64 = base64.b64encode(img_file.read()).decode('utf-8')
    return f"""<div style="display: flex; justify-content: center; margin-bottom: 10px;"><img src="data:image/png;base64,{img_b64}" alt="Logo" style="width: 100%; object-fit: contain;"></div>"""

# --------------------------
# 2. Folium JS Manager
# --------------------------
class MSISManager(MacroElement):
    _template = Template("""
        {% macro script(this, kwargs) %}
        var map = {{ this._parent.get_name() }};
        
        map.createPane('customMapPane'); map.getPane('customMapPane').style.zIndex = 200;
        map.createPane('customOverlayPane'); map.getPane('customOverlayPane').style.zIndex = 400;
        map.createPane('customRobotPane'); map.getPane('customRobotPane').style.zIndex = 600;

        var mapLayer = L.layerGroup().addTo(map);
        var lidarLayer = L.layerGroup().addTo(map);
        var robotLayer = L.layerGroup().addTo(map);
        var axisLayer = L.layerGroup().addTo(map);
        var poiLayer = L.layerGroup().addTo(map);
        
        var currentMapUrl = null;

        if (window.mapData && window.mapData.url) {
            L.imageOverlay(window.mapData.url, window.mapData.bounds, {pane: 'customMapPane'}).addTo(mapLayer);
            map.fitBounds(window.mapData.bounds);
        }

        L.circleMarker([0,0], {radius: 4, color: '#0000FF', fillOpacity: 1, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
        L.polyline([[0,0], [1, 0]], {color: '#FF0000', weight: 4, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
        L.polyline([[0,0], [0, 1]], {color: '#00FF00', weight: 4, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
         
        var scanPolygon = L.polygon([], {
            color: '#FF3366', weight: 0, fillOpacity: 0.2, fillColor: '#FF3366', interactive: false, pane: 'customRobotPane'
        }); 

        map.on('click', function(e) {
            var clickCoords = {x: e.latlng.lng, y: e.latlng.lat};
            var input = window.parent.document.querySelector('#target_coords_json textarea');
            if (input) {
                input.value = JSON.stringify(clickCoords);
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        });
        
        function getJsonFromId(id) {
            var doc = window.parent.document;
            var elem = doc.getElementById(id);
            if (!elem) return null;
            var textArea = elem.querySelector("textarea");
            if (!textArea || !textArea.value) return null;
            try { return JSON.parse(textArea.value); } catch(e) { return null; }
        }

        function updateAllLayers() {
            var poseData = getJsonFromId('json_pose');
            if (poseData && poseData.visible) {
                if (!map.hasLayer(robotLayer)) map.addLayer(robotLayer);
                robotLayer.clearLayers();
                if (poseData.multi_poses) {
                    poseData.multi_poses.forEach(function(r) {
                        var shapes = drawRobot(r.x, r.y, r.yaw, r.name, r.is_selected, r.has_error);
                        shapes.forEach(s => s.addTo(robotLayer));
                    });
                }
            } else if (poseData && !poseData.visible) {
                 if (map.hasLayer(robotLayer)) map.removeLayer(robotLayer);
            }

            var lidarData = getJsonFromId('json_lidar');
            if (lidarData && lidarData.visible) {
                if (!map.hasLayer(lidarLayer)) map.addLayer(lidarLayer);
                if (lidarData.scan && lidarData.pose) {
                    lidarLayer.clearLayers();
                    var rx = lidarData.pose.x;
                    var ry = lidarData.pose.y;
                    var ryaw = lidarData.pose.yaw;
                    var points = lidarData.scan.laser_points;
                    var polyCoords = [[ry, rx]]; 
                    var validPoints = points.filter(p => p.distance > 0.05 && p.distance < 30.0);

                    validPoints.forEach((p, i) => {
                        var ga = p.angle + ryaw; 
                        var wy = ry + p.distance * Math.sin(ga);
                        var wx = rx + p.distance * Math.cos(ga);
                        var coord = [wy, wx];
                        polyCoords.push(coord);
                        if (i % 2 === 0) { 
                            L.circleMarker(coord, {
                                radius: 3, color: '#FF0000', fillOpacity: 0.8, stroke: false, 
                                interactive: false, pane: 'customRobotPane'
                            }).addTo(lidarLayer);
                        }
                    });
                    polyCoords.push([ry, rx]);
                    scanPolygon.setLatLngs(polyCoords);
                    scanPolygon.addTo(lidarLayer);
                }
            } else if (lidarData && !lidarData.visible) {
                if (map.hasLayer(lidarLayer)) map.removeLayer(lidarLayer);
            }

            var mapData = getJsonFromId('json_map');
            if (mapData) {
                if (mapData.visible_map) {
                    if (!map.hasLayer(mapLayer)) map.addLayer(mapLayer);
                    if (mapData.map_url && mapData.map_url !== currentMapUrl) {
                        mapLayer.clearLayers();
                        L.imageOverlay(mapData.map_url, mapData.bounds, {pane: 'customMapPane'}).addTo(mapLayer);
                        if (!currentMapUrl) map.fitBounds(mapData.bounds);
                        currentMapUrl = mapData.map_url;
                    }
                } else {
                    if (map.hasLayer(mapLayer)) map.removeLayer(mapLayer);
                }
                
                if (mapData.visible_axis) {
                    if (!map.hasLayer(axisLayer)) map.addLayer(axisLayer);
                } else {
                    if (map.hasLayer(axisLayer)) map.removeLayer(axisLayer);
                }

                poiLayer.clearLayers();
                if (mapData.pois) {
                    mapData.pois.forEach(p => {
                        L.circleMarker([p.y, p.x], { radius: 6, color: '#0000FF', fillColor: '#2196F3', fillOpacity: 1.0, pane: 'customOverlayPane' })
                         .bindTooltip(p.name, {permanent: false, direction: "top"})
                         .addTo(poiLayer);
                    });
                }
            }
        }
        
        function drawRobot(x, y, yaw, name, isSelected, hasError) {
            var length = 0.74; var width = 0.44;  
            var cornersRel = [[ length/2, width/2], [-length/2, width/2], [-length/2, -width/2], [ length/2, -width/2]];
            var arrowRel = [[ length/2 + 0.15, 0], [ length/2 - 0.1, 0.12], [ length/2 - 0.1, -0.12]];

            function transform(points) {
                return points.map(p => {
                    var rx = p[0]; var ry = p[1];
                    var rotX = rx * Math.cos(yaw) - ry * Math.sin(yaw);
                    var rotY = rx * Math.sin(yaw) + ry * Math.cos(yaw);
                    return [y + rotY, x + rotX];
                });
            }
            var rectCoords = transform(cornersRel);
            var arrowCoords = transform(arrowRel);
            var bodyColor = isSelected ? '#2196F3' : '#9E9E9E'; 
            if (hasError) bodyColor = '#000000';

            var rect = L.polygon(rectCoords, {
                color: 'black', weight: 1, fillColor: bodyColor, fillOpacity: 0.8, 
                interactive: true, pane: 'customRobotPane'
            });
            rect.bindTooltip(name, {permanent: false, direction: "top", offset: [0, -10]});
            var arrow = L.polygon(arrowCoords, {
                color: '#FFEB3B', weight: 1, fillColor: '#FFEB3B', fillOpacity: 1.0, 
                interactive: false, pane: 'customRobotPane'
            });
            return [rect, arrow];
        }

        setInterval(updateAllLayers, 300);
        {% endmacro %}
    """)

# --------------------------
# 3. Backend Logic Functions
# --------------------------
def get_robot_list():
    return list(manager.get_all_robots().keys())

def get_map_view(robot_name=None):
    if not robot_name:
        all_robots = manager.get_all_robots()
        if not all_robots: return "<div style='color:white; padding:20px;'>No Robots Connected</div>"
        target_robot = list(all_robots.values())[0]
    else:
        target_robot = manager.get_robot(robot_name)

    content = target_robot.get_map_explore()
    if not content: return "<div>Map Offline</div>"
    
    grid, meta = parse_grid_and_meta(content)
    img_b64 = generate_map_base64(grid)
    
    bounds = [[meta['min_y'], meta['min_x']], [meta['max_y'], meta['max_x']]]
    center_y = (meta['min_y'] + meta['max_y']) / 2
    center_x = (meta['min_x'] + meta['max_x']) / 2
    
    m = folium.Map(
        location=[center_y, center_x], 
        zoom_start=3, 
        crs="Simple", 
        tiles=None, 
        zoom_control=True,
        attr='MSIS AMR',
        attribution_control=False 
    )
    m.get_root().header.add_child(folium.Element("<style>body, .folium-map { background-color: #808080 !important; }</style>"))
    m.get_root().html.add_child(folium.Element(f"<script>window.mapBounds = {bounds}; window.mapData = {{ url: '{img_b64}', bounds: {bounds} }};</script>"))
    m.add_child(MSISManager())
    return m._repr_html_()

def update_all_loop(selected_robot_name, show_map, show_laser, show_robot, show_axis, poi_list):
    all_robots = manager.get_all_robots()
    target_robot = all_robots.get(selected_robot_name)
    j_pose, j_lidar, j_map = "{}", "{}", "{}"
    pose_str, status_str = "No Pose", "Checking..."

    if target_robot:
        pose = target_robot.get_pose()
        multi_poses = []
        for name, r in all_robots.items():
            p = r.get_pose()
            if p:
                multi_poses.append({"name": name, "x": p["x"], "y": p["y"], "yaw": p["yaw"], "is_selected": (name == selected_robot_name), "has_error": False})
        j_pose = json.dumps({"multi_poses": multi_poses, "visible": show_robot})

        scan = target_robot.get_laser_scan() if show_laser else None
        j_lidar = json.dumps({"scan": scan, "pose": pose, "visible": show_laser})
        
        final_pois = target_robot.get_pois() + (poi_list if poi_list else [])

        j_map = json.dumps({
            "pois": final_pois, 
            "areas": target_robot.get_rectangle_areas("forbidden_area"), 
            "visible_map": show_map, 
            "visible_axis": show_axis,
            "map_url": None, 
            "bounds": None
        })
        
        if pose:
            pose_str = f"📍 {selected_robot_name}: {pose['x']:.2f}, {pose['y']:.2f}"
        status_str = f"Connected: {len(all_robots)}"

    return j_pose, j_lidar, j_map, pose_str, status_str

def add_new_robot(name, ip):
    manager.add_robot(name, ip)
    # UI 업데이트를 위해 갱신된 리스트 반환이 필요할 수 있으나, gradio update는 gui.py에서 처리 권장
    return list(manager.get_all_robots().keys())

def manual_move(name, code):
    r = manager.get_robot(name)
    if r: 
        payload = { "action_name": "slamtec.agent.actions.MoveByAction", "options": { "direction": code, "duration": 500 } }
        r._post("/api/core/motion/v1/actions", payload)

def cmd_stop(name):
    r = manager.get_robot(name)
    if r: r.stop()

# --- Motion & POI Logic ---
def toggle_sidebar(tab_name):
    if tab_name == "Motion":
        return True, False # Motion Visible, Map Visible
    else:
        return False, True

def handle_map_click(json_str, waypoint_list, click_mode):
    if not json_str: return "Wait for click...", waypoint_list, ""
    try:
        coords = json.loads(json_str)
        info_text = f"Selected: X={coords['x']:.2f}, Y={coords['y']:.2f}"
        log_text = ""
        if click_mode == "add_point":
            waypoint_list.append(coords)
        log_lines = [f"{i+1}. ({p['x']:.2f}, {p['y']:.2f})" for i, p in enumerate(waypoint_list)]
        log_text = "\n".join(log_lines)
        return info_text, waypoint_list, log_text
    except Exception as e:
        return f"Error: {e}", waypoint_list, ""

def execute_motion_thread(robot_name, waypoint_list, mode):
    r = manager.get_robot(robot_name)
    if not r: return
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

def trigger_motion(robot_name, waypoint_list, mode):
    if not waypoint_list: return "No waypoints selected."
    t = threading.Thread(target=execute_motion_thread, args=(robot_name, waypoint_list, mode))
    t.start()
    return f"Started {mode} move with {len(waypoint_list)} points."

def clear_waypoints():
    return [], ""

def add_poi_to_list(poi_name, last_click_json, current_pois):
    if not last_click_json:
        return current_pois, current_pois, "⚠️ Click map first!"
    try:
        coords = json.loads(last_click_json)
        new_poi = {
            "x": coords['x'],
            "y": coords['y'],
            "name": poi_name if poi_name else f"POI_{len(current_pois)+1}"
        }
        updated_list = current_pois + [new_poi]
        display_data = [[p['x'], p['y'], p['name']] for p in updated_list]
        return updated_list, display_data, f"✅ Added: {new_poi['name']}"
    except Exception as e:
        return current_pois, [], f"❌ Error: {e}"

def export_pois_to_csv(current_pois):
    if not current_pois: return None
    filename = "POI.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for p in current_pois:
            writer.writerow([p['x'], p['y'], p['name']])
    return filename

def import_pois_from_csv(file_obj):
    if not file_obj: return [], []
    new_pois = []
    try:
        with open(file_obj.name, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3:
                    new_pois.append({
                        "x": float(row[0]),
                        "y": float(row[1]),
                        "name": str(row[2])
                    })
        display_data = [[p['x'], p['y'], p['name']] for p in new_pois]
        return new_pois, display_data
    except Exception as e:
        print(f"CSV Load Error: {e}")
        return [], []

def clear_all_pois():
    return [], []