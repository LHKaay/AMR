import gradio as gr
import folium
import numpy as np
import base64
import struct
import cv2
import json
import os
import time
from branca.element import MacroElement
from jinja2 import Template

from rest_api import manager


# --------------------------
# 1. Map Data Processing & SVG Generation
# --------------------------
def parse_grid_and_meta(content):
    """Parses binary map content into grid and metadata."""
    if not content or len(content) < 36: return None, None
    ox, oy = struct.unpack("<ff", content[0:8])
    nx, ny = struct.unpack("<II", content[8:16])
    res = struct.unpack("<f", content[16:20])[0]
    grid_data = content[36:36 + (nx * ny)]
    grid = np.frombuffer(grid_data, dtype=np.uint8).reshape((ny, nx))
    meta = {'min_x': ox, 'max_x': ox + nx*res, 'min_y': oy, 'max_y': oy + ny*res,
            'width': nx, 'height': ny, 'resolution': res}
    return grid, meta

def generate_map_base64(grid, render_contour=False):
    """Converts grid map to optimized SVG base64 string."""
    h, w = grid.shape
    grid = np.flipud(grid) # Flip to match image coordinates
    
    # Background color (#808080)
    svg_parts = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">']
    svg_parts.append(f'<rect width="{w}" height="{h}" fill="#808080"/>')

    # Draw map data using Run-Length Encoding (RLE) optimization
    for y in range(h):
        row = grid[y]
        current_color = None
        start_x = 0
        run_length = 0
        for x in range(w):
            val = row[x]
            if val > 127: pixel_color = "#000000" # Obstacle
            elif val > 0: pixel_color = "#FFFFFF" # Free Space
            else: pixel_color = None # Unknown (Transparent)

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
    """Returns HTML string for the logo image."""
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
        
        console.log("MSIS Manager Loaded");

        // --- Pane Setup (Z-Index Control) ---
        // Ensures Robot/LiDAR is always on top of the Map
        map.createPane('customMapPane');
        map.getPane('customMapPane').style.zIndex = 200;
        
        map.createPane('customOverlayPane');
        map.getPane('customOverlayPane').style.zIndex = 400;
        
        map.createPane('customRobotPane');
        map.getPane('customRobotPane').style.zIndex = 600;

        // --- Layers ---
        var mapLayer = L.layerGroup().addTo(map);
        var areaLayer = L.layerGroup().addTo(map);
        var poiLayer = L.layerGroup().addTo(map);
        var robotLayer = L.layerGroup().addTo(map);
        var lidarLayer = L.layerGroup().addTo(map);
        var axisLayer = L.layerGroup().addTo(map);
        
        var currentMapUrl = null;

        // --- Initial Map Load ---
        if (window.mapData && window.mapData.url) {
            L.imageOverlay(window.mapData.url, window.mapData.bounds, {pane: 'customMapPane'}).addTo(mapLayer);
            map.fitBounds(window.mapData.bounds);
        }

        // --- Static Axis ---
        L.circleMarker([0,0], {radius: 4, color: '#0000FF', fillOpacity: 1, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
        L.polyline([[0,0], [1, 0]], {color: '#FF0000', weight: 4, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
        L.polyline([[0,0], [0, 1]], {color: '#00FF00', weight: 4, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
         
        // Polygon for LiDAR scan area
        var scanPolygon = L.polygon([], {
            color: '#FF3366', weight: 0, fillOpacity: 0.2, fillColor: '#FF3366', interactive: false, pane: 'customRobotPane'
        }); 
        
        // Helper to safely parse JSON from DOM
        function getJsonFromId(id) {
            var doc = window.parent.document;
            var elem = doc.getElementById(id);
            if (!elem) return null;
            var textArea = elem.querySelector("textarea");
            if (!textArea || !textArea.value) return null;
            try { return JSON.parse(textArea.value); } catch(e) { return null; }
        }

        // ----------------------------------------------------
        // Unified Update Function (Performance Optimized)
        // ----------------------------------------------------
        function updateAllLayers() {
            // 1. Robot Pose
            var poseData = getJsonFromId('json_pose');
            if (poseData) {
                if (poseData.visible) {
                    if (!map.hasLayer(robotLayer)) map.addLayer(robotLayer);
                    robotLayer.clearLayers();
                    if (poseData.multi_poses) {
                        poseData.multi_poses.forEach(function(r) {
                            var shapes = drawRobot(r.x, r.y, r.yaw, r.name, r.is_selected, r.has_error);
                            shapes.forEach(s => s.addTo(robotLayer));
                        });
                    }
                } else {
                    if (map.hasLayer(robotLayer)) map.removeLayer(robotLayer);
                }
            }

            // 2. LiDAR
            var lidarData = getJsonFromId('json_lidar');
            if (lidarData) {
                if (lidarData.visible) {
                    if (!map.hasLayer(lidarLayer)) map.addLayer(lidarLayer);
                    if (lidarData.scan && lidarData.pose) {
                        lidarLayer.clearLayers();
                        
                        var rx = lidarData.pose.x;
                        var ry = lidarData.pose.y;
                        var ryaw = lidarData.pose.yaw;
                        var points = lidarData.scan.laser_points;
                        
                        // Start Polygon at Robot Center
                        var polyCoords = [[ry, rx]]; 
                        
                        // Filter invalid points to prevent artifacts (Max range 30m)
                        var validPoints = points.filter(p => p.distance > 0.05 && p.distance < 30.0);

                        validPoints.forEach((p, i) => {
                            var ga = p.angle + ryaw; 
                            var wy = ry + p.distance * Math.sin(ga);
                            var wx = rx + p.distance * Math.cos(ga);
                            var coord = [wy, wx];
                            
                            polyCoords.push(coord);
                            
                            // Draw fewer dots for performance (every 2nd point)
                            if (i % 2 === 0) { 
                                L.circleMarker(coord, {
                                    radius: 3, color: '#FF0000', fillOpacity: 0.8, stroke: false, 
                                    interactive: false, pane: 'customRobotPane'
                                }).addTo(lidarLayer);
                            }
                        });
                        
                        // Close Polygon back to Robot Center
                        polyCoords.push([ry, rx]);
                        
                        scanPolygon.setLatLngs(polyCoords);
                        scanPolygon.addTo(lidarLayer);
                    }
                } else {
                    if (map.hasLayer(lidarLayer)) map.removeLayer(lidarLayer);
                }
            }

            // 3. Map & Static
            var mapData = getJsonFromId('json_map');
            if (mapData) {
                // Map Image
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
                
                // Axis
                if (mapData.visible_axis) {
                    if (!map.hasLayer(axisLayer)) map.addLayer(axisLayer);
                } else {
                    if (map.hasLayer(axisLayer)) map.removeLayer(axisLayer);
                }
                
                // Redraw Areas/POIs only if needed (simplified here)
            }
        }
        
        // Draw Robot: Rect + Triangle
        function drawRobot(x, y, yaw, name, isSelected, hasError) {
            var length = 0.74; var width = 0.44;  
            var cornersRel = [[ length/2, width/2], [-length/2, width/2], [-length/2, -width/2], [ length/2, -width/2]];
            
            // Triangle indicating heading
            var arrowRel = [[ length/2 + 0.15, 0], [ length/2 - 0.1, 0.12], [ length/2 - 0.1, -0.12]];

            function transform(points) {
                return points.map(p => {
                    var rx = p[0]; var ry = p[1];
                    var rotX = rx * Math.cos(yaw) - ry * Math.sin(yaw);
                    var rotY = rx * Math.sin(yaw) + ry * Math.cos(yaw);
                    // Leaflet [Y, X]
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

        // Single Interval for everything to reduce connection load (300ms)
        setInterval(updateAllLayers, 300);
        {% endmacro %}
    """)

# --------------------------
# 3. Backend Logic
# --------------------------
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

    m.get_root().header.add_child(folium.Element(
        "<style>body, .folium-map { background-color: #808080 !important; }</style>"
    ))
    m.get_root().html.add_child(folium.Element(
        f"<script>window.mapBounds = {bounds}; window.mapData = {{ url: '{img_b64}', bounds: {bounds} }};</script>"
    ))
    m.add_child(MSISManager())
    return m._repr_html_()

# Unified Update Function (Prevents Connection Refused by reducing requests)
def update_all_loop(selected_robot_name, show_map, show_laser, show_robot, show_axis):
    all_robots = manager.get_all_robots()
    target_robot = all_robots.get(selected_robot_name)
    
    # Defaults
    j_pose, j_lidar, j_map = "{}", "{}", "{}"
    pose_str, status_str = "No Pose", "Checking..."

    if target_robot:
        # 1. Pose
        pose = target_robot.get_pose()
        multi_poses = []
        for name, r in all_robots.items():
            p = r.get_pose()
            if p:
                multi_poses.append({"name": name, "x": p["x"], "y": p["y"], "yaw": p["yaw"], "is_selected": (name == selected_robot_name), "has_error": False})
        j_pose = json.dumps({"multi_poses": multi_poses, "visible": show_robot})

        # 2. LiDAR
        scan = target_robot.get_laser_scan() if show_laser else None
        j_lidar = json.dumps({"scan": scan, "pose": pose, "visible": show_laser})
        
        # 3. Map (Only URL if needed, mostly static data)
        # To save bandwidth, we don't send map image every 0.3s unless needed.
        # Here we only send Map Image if 'show_map' is toggled on, but ideally check change.
        # For simplicity in this fix, we assume Map doesn't change often.
        map_url = None
        bounds = None
        if show_map:
             # Only fetch map if really needed (optimization)
             # content = target_robot.get_map_explore() ... (Too heavy for 0.3s)
             pass 

        j_map = json.dumps({
            "pois": target_robot.get_pois(), 
            "areas": target_robot.get_rectangle_areas("forbidden_area"), 
            "visible_map": show_map, 
            "visible_axis": show_axis,
            "map_url": map_url, 
            "bounds": bounds
        })
        
        if pose:
            pose_str = f"📍 {selected_robot_name}: {pose['x']:.2f}, {pose['y']:.2f}"
        status_str = f"Connected: {len(all_robots)}"

    return j_pose, j_lidar, j_map, pose_str, status_str

def add_new_robot(name, ip):
    manager.add_robot(name, ip)
    return gr.update(choices=list(manager.get_all_robots().keys()), value=name), f"Added {name}"

def manual_move(name, code):
    r = manager.get_robot(name)
    if r: 
        payload = { "action_name": "slamtec.agent.actions.MoveByAction", "options": { "direction": code, "duration": 500 } }
        r._post("/api/core/motion/v1/actions", payload)

def cmd_stop(name):
    r = manager.get_robot(name)
    if r: r.stop()

# --------------------------
# 4. GUI Setup
# --------------------------
custom_css = """
.gradio-container { max-width: 100% !important; padding: 0 !important; margin: 0 !important; background-color: #808080 !important; }
body { margin: 0; padding: 0; background-color: #808080 !important; }
footer { display: none !important; }
.leaflet-control-attribution { display: none !important; }
/* Keep hidden elements in DOM for JS access */
.hidden-elem { display: none !important; }
#top_menu { background-color: #808080 !important; color: #FFFFFF !important; padding: 10px 25px; border-bottom: none; }
.menu_btn { background: none !important; border: none !important; color: #FFFFFF !important; font-weight: 700 !important; cursor: pointer; font-size: 16px !important; }
.menu_btn:hover { color: #4CAF50 !important; }
#sidebar { background-color: #ffffff !important; border-right: 1px solid #dcdcdc !important; padding: 20px !important; }
.section-header { color: #2c3e50; border-bottom: 2px solid #2196F3; padding-bottom: 5px; margin-top: 20px; font-weight: bold; }
button { border-radius: 6px !important; font-weight: 600 !important; }
.btn-nav { background-color: #f5f5f5 !important; font-size: 20px !important; height: 50px !important; }
.btn-nav:hover { background-color: #4CAF50 !important; color: white !important; }
.btn-stop { background-color: #212121 !important; color: white !important; }
.btn-primary-custom { background-color: #2196F3 !important; color: white !important; }
.dpad-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; width: 180px; margin: 10px auto; }
iframe { height: 93vh !important; width: 100% !important; border: none !important; background-color: #808080 !important; }
"""

js_loader = """function() { console.log("UI Loaded"); }"""
robot_names = list(manager.get_all_robots().keys())
init_val = robot_names[0] if robot_names else None

with gr.Blocks(title="MSIS Control Studio") as demo:
    with gr.Row(elem_id="top_menu"):
        gr.Button("Motion", elem_classes="menu_btn")
        gr.Button("MAP", elem_classes="menu_btn")
        gr.Button("ARM", elem_classes="menu_btn")
        gr.Button("CAMERA", elem_classes="menu_btn")

    with gr.Row():
        with gr.Sidebar(elem_id="sidebar", width=350):
            gr.HTML(get_logo_html("MSIS_WB_logo.png"))
            gr.Markdown("## 🤖 MSIS Manager", elem_classes=["section-header"])
            robot_dropdown = gr.Dropdown(choices=robot_names, value=init_val, label="Select Target Robot")
            
            with gr.Accordion("➕ Add Robot", open=False):
                with gr.Row():
                    txt_name = gr.Textbox(label="Name", placeholder="AMR_01")
                    txt_ip = gr.Textbox(label="IP", placeholder="192.168.0.x")
                btn_add_robot = gr.Button("Add", elem_classes=["btn-primary-custom"])
                msg_box = gr.Markdown("")

            with gr.Row():
                status_display = gr.Markdown("🔋 Status: Checking...")

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

            gr.Markdown("👁️ Layers", elem_classes=["section-header"])
            with gr.Row():
                chk_map = gr.Checkbox(label="Map", value=True)
                chk_laser = gr.Checkbox(label="Laser", value=True)
            with gr.Row():
                chk_robot = gr.Checkbox(label="Robot", value=True)
                chk_axis = gr.Checkbox(label="Axis", value=False)
            
            pose_display = gr.Markdown("Position: ...")

        with gr.Column(elem_id="map-container"):
            map_html = gr.HTML(value=get_map_view(init_val))
            # Hidden inputs (visible=True + CSS hidden)
            json_pose = gr.Textbox(elem_id="json_pose", visible=True, elem_classes=["hidden-elem"])
            json_lidar = gr.Textbox(elem_id="json_lidar", visible=True, elem_classes=["hidden-elem"])
            json_map = gr.Textbox(elem_id="json_map", visible=True, elem_classes=["hidden-elem"])

    # Events
    btn_add_robot.click(add_new_robot, [txt_name, txt_ip], [robot_dropdown, msg_box])
    btn_up.click(lambda r: manual_move(r, 0), [robot_dropdown], None)
    btn_down.click(lambda r: manual_move(r, 1), [robot_dropdown], None)
    btn_left.click(lambda r: manual_move(r, 3), [robot_dropdown], None)
    btn_right.click(lambda r: manual_move(r, 2), [robot_dropdown], None)
    btn_stop.click(cmd_stop, [robot_dropdown], None)

    # Combined Timer (Safe Update) - 0.2s is safer for preventing connection refused
    timer = gr.Timer(value=0.2)
    timer.tick(
        update_all_loop,
        inputs=[robot_dropdown, chk_map, chk_laser, chk_robot, chk_axis],
        outputs=[json_pose, json_lidar, json_map, pose_display, status_display]
    )

    demo.load(None, None, None, js=js_loader)

if __name__ == "__main__":
    demo.launch(css=custom_css)
