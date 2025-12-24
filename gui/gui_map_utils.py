# gui/gui_map_utils.py
import struct
import numpy as np
import base64
import os
import folium
from branca.element import MacroElement
from jinja2 import Template

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
        alt_path = os.path.join("..", image_path)
        if os.path.exists(alt_path):
            image_path = alt_path
        else:
            return f"<div style='height:10px;'></div>"
    with open(image_path, "rb") as img_file:
        img_b64 = base64.b64encode(img_file.read()).decode('utf-8')
    return f"""<div style="display: flex; justify-content: center; margin-bottom: 10px;"><img src="data:image/png;base64,{img_b64}" alt="Logo" style="width: 100%; object-fit: contain;"></div>"""

# --------------------------
# 2. Folium JS Manager (Fixed LiDAR Logic)
# --------------------------
class MSISManager(MacroElement):
    _template = Template("""
        {% macro script(this, kwargs) %}
        var map = {{ this._parent.get_name() }};
        
        // 1. Pane 설정 (Z-Index: 로봇과 라이다를 가장 위로)
        map.createPane('customMapPane'); map.getPane('customMapPane').style.zIndex = 200;
        map.createPane('customOverlayPane'); map.getPane('customOverlayPane').style.zIndex = 400;
        map.createPane('customRobotPane'); map.getPane('customRobotPane').style.zIndex = 600;

        // 2. 레이어 그룹 생성
        var mapLayer = L.layerGroup().addTo(map);
        var lidarLayer = L.layerGroup().addTo(map);
        var robotLayer = L.layerGroup().addTo(map);
        var axisLayer = L.layerGroup().addTo(map);
        var poiLayer = L.layerGroup().addTo(map);
        
        var currentMapUrl = null;

        // 초기 맵 로드
        if (window.mapData && window.mapData.url) {
            L.imageOverlay(window.mapData.url, window.mapData.bounds, {pane: 'customMapPane'}).addTo(mapLayer);
            map.fitBounds(window.mapData.bounds);
        }

        // 기준 축 그리기
        L.circleMarker([0,0], {radius: 4, color: '#0000FF', fillOpacity: 1, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
        L.polyline([[0,0], [1, 0]], {color: '#FF0000', weight: 4, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
        L.polyline([[0,0], [0, 1]], {color: '#00FF00', weight: 4, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
         
        // 라이다 폴리곤 객체 (Pane 지정 필수)
        var scanPolygon = L.polygon([], {
            color: '#FF3366', 
            weight: 1, 
            fillOpacity: 0.2, 
            fillColor: '#FF3366', 
            interactive: false, 
            pane: 'customRobotPane'
        }); 

        // 맵 클릭 이벤트
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
            // [Robot Pose]
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

            // [LiDAR]
            var lidarData = getJsonFromId('json_lidar');
            if (lidarData && lidarData.visible) {
                if (!map.hasLayer(lidarLayer)) map.addLayer(lidarLayer);
                
                // 데이터 체크: pose가 있고, scan 데이터(배열)가 있는지 확인
                if (lidarData.pose && lidarData.scan) {
                    // API마다 필드명이 다를 수 있어 호환성 체크 (laser_points or points)
                    var rawPoints = lidarData.scan.laser_points || lidarData.scan.points;
                    
                    if (rawPoints && rawPoints.length > 0) {
                        lidarLayer.clearLayers();
                        
                        var rx = lidarData.pose.x;
                        var ry = lidarData.pose.y;
                        var ryaw = lidarData.pose.yaw; // 보통 Radian 단위
                        
                        var polyCoords = [[ry, rx]]; // 시작점: 로봇 중심
                        
                        // 디버깅용: 데이터가 들어오는지 콘솔 확인 (F12)
                        // console.log("LiDAR Points:", rawPoints.length);

                        rawPoints.forEach((p, i) => {
                            // 1. 거리 필드 호환성 (dist vs distance)
                            var dist = (p.dist !== undefined) ? p.dist : p.distance;
                            
                            // 2. 각도 필드 호환성 (angle vs a)
                            var angle_raw = (p.angle !== undefined) ? p.angle : p.a;
                            
                            // 유효성 검사 (너무 짧거나 너무 먼 거리 제외)
                            if (dist > 0.05 && dist < 40.0 && angle_raw !== undefined) {
                                
                                // [중요] 각도 변환: Degree -> Radian
                                // 대부분의 라이다 API는 각도를 도(Degree) 단위로 줍니다.
                                var angle_rad = angle_raw * (Math.PI / 180.0);
                                
                                // 로봇의 헤딩(ryaw)을 더해 글로벌 각도 계산
                                var global_angle = angle_rad + ryaw;
                                
                                // 좌표 계산 (Standard Trigonometry)
                                // Leaflet은 [Y(Lat), X(Lng)] 순서임에 주의
                                var wy = ry + dist * Math.sin(global_angle);
                                var wx = rx + dist * Math.cos(global_angle);
                                var coord = [wy, wx]; 
                                
                                polyCoords.push(coord);
                                
                                // 성능을 위해 점(CircleMarker)은 3개당 1개만 그리기
                                if (i % 3 === 0) { 
                                    L.circleMarker(coord, {
                                        radius: 2, 
                                        color: '#FF0000', 
                                        fillOpacity: 0.6, 
                                        stroke: false, 
                                        interactive: false, 
                                        pane: 'customRobotPane' 
                                    }).addTo(lidarLayer);
                                }
                            }
                        });
                        
                        // 폴리곤 닫기 (로봇 중심으로)
                        polyCoords.push([ry, rx]);
                        
                        // 폴리곤 업데이트 및 레이어에 추가
                        scanPolygon.setLatLngs(polyCoords);
                        if (!lidarLayer.hasLayer(scanPolygon)) {
                            scanPolygon.addTo(lidarLayer);
                        }
                    }
                }
            } else if (lidarData && !lidarData.visible) {
                if (map.hasLayer(lidarLayer)) map.removeLayer(lidarLayer);
            }

            // [Map & POI]
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
                        L.circleMarker([p.y, p.x], { 
                            radius: 6, color: '#0000FF', fillColor: '#2196F3', fillOpacity: 1.0, pane: 'customOverlayPane' 
                        })
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

def get_map_view(robot_name, manager):
    if not robot_name:
        all_robots = manager.get_all_robots()
        if not all_robots: return "<div style='color:white; padding:20px;'>No Robots Connected</div>"
        target_robot = list(all_robots.values())[0]
    else:
        target_robot = manager.get_robot(robot_name)
    
    if not target_robot: return "<div>Robot Offline</div>"

    content = target_robot.get_map_explore()
    if not content: return "<div>Map Offline</div>"
    
    grid, meta = parse_grid_and_meta(content)
    img_b64 = generate_map_base64(grid)
    bounds = [[meta['min_y'], meta['min_x']], [meta['max_y'], meta['max_x']]]
    center_y = (meta['min_y'] + meta['max_y']) / 2
    center_x = (meta['min_x'] + meta['max_x']) / 2
    
    m = folium.Map(location=[center_y, center_x], zoom_start=3, crs="Simple", tiles=None, zoom_control=True, attr='MSIS AMR', attribution_control=False)
    m.get_root().header.add_child(folium.Element("<style>body, .folium-map { background-color: #808080 !important; }</style>"))
    m.get_root().html.add_child(folium.Element(f"<script>window.mapBounds = {bounds}; window.mapData = {{ url: '{img_b64}', bounds: {bounds} }};</script>"))
    m.add_child(MSISManager())
    return m._repr_html_()