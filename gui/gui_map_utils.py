import struct
import numpy as np
import base64
import os
import folium
from branca.element import MacroElement
from jinja2 import Template

def parse_grid_and_meta(content):
    if not content or len(content) < 36: return None, None
    ox, oy = struct.unpack("<ff", content[0:8])
    nx, ny = struct.unpack("<II", content[8:16])
    res = struct.unpack("<f", content[16:20])[0]
    grid_data = content[36:36 + (nx * ny)]
    grid = np.frombuffer(grid_data, dtype=np.uint8).reshape((ny, nx))
    meta = {'min_x': ox, 'max_x': ox + nx*res, 'min_y': oy, 'max_y': oy + ny*res, 'width': nx, 'height': ny, 'resolution': res}
    return grid, meta

def generate_map_base64(grid):
    h, w = grid.shape; grid = np.flipud(grid)
    svg_parts = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">', f'<rect width="{w}" height="{h}" fill="#808080"/>']
    for y in range(h):
        row = grid[y]; current_color = None; start_x = 0; run_length = 0
        for x in range(w):
            val = row[x]; pixel_color = "#000000" if val > 127 else "#FFFFFF" if val > 0 else None
            if pixel_color == current_color: run_length += 1
            else:
                if current_color is not None: svg_parts.append(f'<rect x="{start_x}" y="{y}" width="{run_length}" height="1" fill="{current_color}"/>')
                current_color = pixel_color; start_x = x; run_length = 1
        if current_color is not None: svg_parts.append(f'<rect x="{start_x}" y="{y}" width="{run_length}" height="1" fill="{current_color}"/>')
    svg_parts.append('</svg>'); svg_str = "".join(svg_parts)
    return f"data:image/svg+xml;base64,{base64.b64encode(svg_str.encode('utf-8')).decode()}"

def get_logo_html(image_path):
    if not os.path.exists(image_path):
        alt_path = os.path.join("..", image_path); image_path = alt_path if os.path.exists(alt_path) else None
    if not image_path: return f"<div style='height:10px;'></div>"
    with open(image_path, "rb") as img_file: img_b64 = base64.b64encode(img_file.read()).decode('utf-8')
    return f"""<div style="display: flex; justify-content: center; margin-bottom: 10px;"><img src="data:image/png;base64,{img_b64}" alt="Logo" style="width: 100%; object-fit: contain;"></div>"""

def get_dock_icon_b64():
    possible_paths = ["map_icon/dock.jpg", "dock.jpg"]
    icon_path = None
    for p in possible_paths:
        if os.path.exists(p):
            icon_path = p
            break 
    if icon_path:
        try:
            with open(icon_path, "rb") as f:
                ext = os.path.splitext(icon_path)[1].lower().replace('.', '')
                if ext == 'jpg': ext = 'jpeg'
                return f"data:image/{ext};base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception as e: print(f"Error loading dock icon: {e}")
    return None

class MSISManager(MacroElement):
    def __init__(self):
        super(MSISManager, self).__init__()
        self.dock_icon_src = get_dock_icon_b64()
        dock_icon_js = f"'{self.dock_icon_src}'" if self.dock_icon_src else "null"
        
        self._template = Template("""
        {% macro script(this, kwargs) %}
        var map = {{ this._parent.get_name() }};
        var dockIconSrc = """ + dock_icon_js + """;

        map.createPane('customMapPane'); map.getPane('customMapPane').style.zIndex = 200;
        map.createPane('customLidarPane'); map.getPane('customLidarPane').style.zIndex = 300;
        map.createPane('customOverlayPane'); map.getPane('customOverlayPane').style.zIndex = 400;
        map.createPane('customAreaPane'); map.getPane('customAreaPane').style.zIndex = 500; 
        map.createPane('customLinePane'); map.getPane('customLinePane').style.zIndex = 550; 
        map.createPane('customRobotPane'); map.getPane('customRobotPane').style.zIndex = 600;
        
        var mapLayer = L.layerGroup().addTo(map); var lidarRayLayer = L.layerGroup().addTo(map);   
        var lidarPointLayer = L.layerGroup().addTo(map); var robotLayer = L.layerGroup().addTo(map);
        var axisLayer = L.layerGroup().addTo(map); var poiLayer = L.layerGroup().addTo(map);
        var dockLayer = L.layerGroup().addTo(map); 
        var waypointLayer = L.layerGroup().addTo(map); var trajectoryLayer = L.layerGroup().addTo(map);
        var pathPlanLayer = L.layerGroup().addTo(map); var areaLayer = L.layerGroup().addTo(map); var lineLayer = L.layerGroup().addTo(map);
        var tempLayer = L.layerGroup().addTo(map); var clickLayer = L.layerGroup().addTo(map);
        var currentMapUrl = null;

        // [SVG Icons]
        var bluePinSvg = encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="blue" stroke="white" stroke-width="2"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>');
        var bluePinIcon = L.icon({ iconUrl: 'data:image/svg+xml;charset=utf-8,' + bluePinSvg, iconSize: [24, 24], iconAnchor: [12, 24], popupAnchor: [0, -24], tooltipAnchor: [0, -24] });

        var redPinSvg = encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="red" stroke="white" stroke-width="2"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>');
        var redPinIcon = L.icon({ iconUrl: 'data:image/svg+xml;charset=utf-8,' + redPinSvg, iconSize: [28, 28], iconAnchor: [14, 28], popupAnchor: [0, -28], tooltipAnchor: [0, -28] });

        if (window.mapData && window.mapData.url) {
            L.imageOverlay(window.mapData.url, window.mapData.bounds, {pane: 'customMapPane'}).addTo(mapLayer);
            map.fitBounds(window.mapData.bounds);
        }
        L.circleMarker([0,0], {radius: 4, color: '#0000FF', fillOpacity: 1, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
        L.polyline([[0,0], [1, 0]], {color: '#FF0000', weight: 4, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
        L.polyline([[0,0], [0, 1]], {color: '#00FF00', weight: 4, interactive: false, pane: 'customOverlayPane'}).addTo(axisLayer);
        var scanRays = L.polyline([], {color: '#FF0000', weight: 1, opacity: 0.3, pane: 'customLidarPane', interactive: false});

        map.on('click', function(e) {
            var clickCoords = {x: e.latlng.lng, y: e.latlng.lat};
            var input = window.parent.document.querySelector('#target_coords_json textarea');
            if (input) { input.value = JSON.stringify(clickCoords); input.dispatchEvent(new Event('input', { bubbles: true })); }
            clickLayer.clearLayers(); L.circleMarker(e.latlng, {radius: 5, color: '#2F0EC2', fillColor: '#11FF00', fillOpacity: 1.0, pane: 'customOverlayPane'}).addTo(clickLayer);
        });
        
        function getJsonFromId(id) {
            var doc = window.parent.document; var elem = doc.getElementById(id); if (!elem) return null;
            var input = elem.querySelector("textarea") || elem.querySelector("input"); if (!input) return null;
            try { return JSON.parse(input.value || input.innerText); } catch(e) { return null; }
        }

        // [Helper] Rect Corners
        function getRectCorners(start, end, half_width) {
            var dx = end.x - start.x; var dy = end.y - start.y; var len = Math.sqrt(dx*dx + dy*dy);
            if (len === 0) return null;
            var nx = -dy / len; var ny = dx / len;
            return [[start.y + ny * half_width, start.x + nx * half_width], [end.y + ny * half_width, end.x + nx * half_width],
                    [end.y - ny * half_width, end.x - nx * half_width], [start.y - ny * half_width, start.x - nx * half_width]];
        }

        // [Helper] Inner Rect for Forbidden Area
        function getInnerRectCorners(start, end, half_width, escape_dist) {
            if (escape_dist >= half_width) return null; 
            var dx = end.x - start.x; var dy = end.y - start.y; var len = Math.sqrt(dx*dx + dy*dy);
            if (len <= 2 * escape_dist) return null;

            var ux = dx / len; var uy = dy / len; 
            var nx = -uy; var ny = ux; 

            var new_half_width = half_width - escape_dist;
            var sx = start.x + ux * escape_dist; var sy = start.y + uy * escape_dist;
            var ex = end.x - ux * escape_dist; var ey = end.y - uy * escape_dist;

            return [[sy + ny * new_half_width, sx + nx * new_half_width], [ey + ny * new_half_width, ex + nx * new_half_width],
                    [ey - ny * new_half_width, ex - nx * new_half_width], [sy - ny * new_half_width, sx - nx * new_half_width]];
        }

        // [Helper] Elevator Door Corners
        function getDoorCorners(start, end, half_width, doorDepth, direction) {
            var dx = end.x - start.x; var dy = end.y - start.y; var len = Math.sqrt(dx*dx + dy*dy);
            if (len === 0) return null;
            var nx = -dy / len; var ny = dx / len; 
            var ux = dx / len; var uy = dy / len; 
            
            var basePoint, dirSign;
            if (direction === 1) { basePoint = start; dirSign = -1; } 
            else { basePoint = end; dirSign = 1; } 

            var p1 = [basePoint.y + ny * half_width, basePoint.x + nx * half_width];
            var p2 = [basePoint.y - ny * half_width, basePoint.x - nx * half_width];
            var p3 = [p2[0] + uy * dirSign * doorDepth, p2[1] + ux * dirSign * doorDepth];
            var p4 = [p1[0] + uy * dirSign * doorDepth, p1[1] + ux * dirSign * doorDepth];
            return [p1, p2, p3, p4];
        }
        
        var areaColors = { 'forbidden_area': '#FF0000', 'elevator_area': '#00FFFF', 'dangerous_area': '#FFA500', 'coverage_area': '#0000FF', 'sensor_disable_area': '#800080', 'restricted_area': '#FFFF00', 'maintenance_area': '#008000', 'default': '#808080' };
        var lineStyles = { 'walls': { color: '#FF0000', weight: 5, opacity: 1.0, pane: 'customLinePane' }, 'tracks': { color: '#00FF00', weight: 4, opacity: 1.0, pane: 'customLinePane' } };

        function updateAllLayers() {
            var poseData = getJsonFromId('json_pose');
            if (poseData && poseData.visible) {
                if (!map.hasLayer(robotLayer)) map.addLayer(robotLayer); robotLayer.clearLayers();
                if (poseData.multi_poses) { poseData.multi_poses.forEach(r => drawRobot(r.x, r.y, r.yaw, r.name, r.is_selected).forEach(s => s.addTo(robotLayer))); }
            } else { if (map.hasLayer(robotLayer)) map.removeLayer(robotLayer); }

            var lidarData = getJsonFromId('json_lidar');
            if (map.hasLayer(lidarRayLayer)) lidarRayLayer.clearLayers();
            if (map.hasLayer(lidarPointLayer)) lidarPointLayer.clearLayers();
            if (lidarData && lidarData.visible) {
                if (lidarData.scan) {
                    var scanObj = lidarData.scan; var points = scanObj.laser_points;
                    if (points && points.length > 0) {
                        var rx = 0, ry = 0, ryaw = 0;
                        if (scanObj.pose) { rx = scanObj.pose.x; ry = scanObj.pose.y; ryaw = scanObj.pose.yaw; } 
                        else if (lidarData.pose) { rx = lidarData.pose.x; ry = lidarData.pose.y; ryaw = lidarData.pose.yaw; }
                        var rayPoints = []; var center = [ry, rx];
                        points.forEach((p, i) => {
                            if (p.valid === false) return;
                            var dist = p.distance; if (dist > 0.05 && dist < 40.0) {
                                if (i % 2 !== 0) return; 
                                var global_angle = p.angle + ryaw;
                                var wy = ry + dist * Math.sin(global_angle); var wx = rx + dist * Math.cos(global_angle);
                                var ptCoords = [wy, wx];
                                if (lidarData.visible_rays) { rayPoints.push(center); rayPoints.push(ptCoords); rayPoints.push(center); }
                                if (lidarData.visible_points) { L.circleMarker(ptCoords, { radius: 2, color: '#FF0000', fillColor: '#FF0000', fillOpacity: 1.0, stroke: false, pane: 'customLidarPane', interactive: false }).addTo(lidarPointLayer); }
                            }
                        });
                        if (lidarData.visible_rays) { if (!map.hasLayer(lidarRayLayer)) map.addLayer(lidarRayLayer); scanRays.setLatLngs(rayPoints); scanRays.addTo(lidarRayLayer); } else { if (map.hasLayer(lidarRayLayer)) map.removeLayer(lidarRayLayer); }
                        if (lidarData.visible_points) { if (!map.hasLayer(lidarPointLayer)) map.addLayer(lidarPointLayer); } else { if (map.hasLayer(lidarPointLayer)) map.removeLayer(lidarPointLayer); }
                    }
                }
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
                } else { if (map.hasLayer(mapLayer)) map.removeLayer(mapLayer); }
                if (mapData.visible_axis) { if (!map.hasLayer(axisLayer)) map.addLayer(axisLayer); } else { if (map.hasLayer(axisLayer)) map.removeLayer(axisLayer); }
                
                // [UPDATED] POI Visualization: Red Pin + Clean Arrow
                poiLayer.clearLayers(); 
                if (mapData.pois) { 
                    mapData.pois.forEach(p => { 
                        var meta = p.metadata || {};
                        // Display Name Logic: Name -> ID
                        var name = meta.display_name;
                        if (!name || name.trim() === "") { name = p.id || "POI"; }
                        
                        var pose = p.pose || p;
                        var yaw = pose.yaw || 0;
                        
                        // 1. Red Pin (Tooltip: Hover only)
                        L.marker([pose.y, pose.x], { icon: redPinIcon, pane: 'customOverlayPane' })
                         .bindTooltip(name, {permanent: false, direction: "top", offset: [0, -28], opacity: 0.9, sticky: true}).addTo(poiLayer);
                        
                        // 2. Direction Arrow (Clean Vector)
                        var arrowLen = 0.2; // Length ~ 2x Pin Base
                        var endX = pose.x + arrowLen * Math.cos(yaw);
                        var endY = pose.y + arrowLen * Math.sin(yaw);
                        
                        // Shaft
                        L.polyline([[pose.y, pose.x], [endY, endX]], {color: '#FF0000', weight: 2, pane: 'customOverlayPane'}).addTo(poiLayer);
                        
                        // Arrowhead (Filled Triangle)
                        var headLen = 0.1; 
                        var angle = Math.atan2(endY - pose.y, endX - pose.x);
                        var angle1 = angle - Math.PI / 6;
                        var angle2 = angle + Math.PI / 6;
                        
                        var p1 = [endY - headLen * Math.sin(angle1), endX - headLen * Math.cos(angle1)];
                        var p2 = [endY - headLen * Math.sin(angle2), endX - headLen * Math.cos(angle2)];
                        var tip = [endY, endX];
                        
                        L.polygon([p1, tip, p2], {color: '#FF0000', weight: 1, fillColor: '#FF0000', fillOpacity: 1, pane: 'customOverlayPane'}).addTo(poiLayer);
                    }); 
                }
                
                dockLayer.clearLayers();
                if (mapData.docks) {
                    mapData.docks.forEach(d => {
                        var name = (d.metadata && d.metadata.display_name) ? d.metadata.display_name : "Dock";
                        var pose = d.pose;
                        var dockIcon;
                        if (dockIconSrc) {
                            dockIcon = L.icon({ iconUrl: dockIconSrc, iconSize: [24, 24], iconAnchor: [12, 12], popupAnchor: [0, -12] });
                        } else {
                            dockIcon = L.divIcon({html: '<div style="font-size:20px;">🏠</div>', className: 'dock-icon', iconSize: [24, 24]});
                        }
                        L.marker([pose.y, pose.x], {icon: dockIcon, pane: 'customOverlayPane'})
                         .bindTooltip(name, {permanent: true, direction: "bottom", offset: [0, 5]}).addTo(dockLayer);
                    });
                }

                waypointLayer.clearLayers(); if (mapData.waypoints) { var pathCoords = mapData.waypoints.map(w => [w.y, w.x]); L.polyline(pathCoords, { color: '#0000FF', weight: 4, dashArray: '10, 10', pane: 'customOverlayPane' }).addTo(waypointLayer); mapData.waypoints.forEach(w => { L.circleMarker([w.y, w.x], { radius: 4, color: '#00008B', fillColor: '#00FFFF', fillOpacity: 1.0, pane: 'customOverlayPane' }).addTo(waypointLayer); }); }
                trajectoryLayer.clearLayers(); if (mapData.trajectory && mapData.trajectory.length > 1) { var trajCoords = mapData.trajectory.map(t => [t.y, t.x]); L.polyline(trajCoords, { color: '#FF00FF', weight: 2, opacity: 0.7, dashArray: '5, 5', pane: 'customOverlayPane' }).addTo(trajectoryLayer); }
                pathPlanLayer.clearLayers();
                if (mapData.planned_path && mapData.planned_path.length > 0) {
                    var pathPts = mapData.planned_path.map(p => [p[1], p[0]]);
                    L.polyline(pathPts, {color: 'lime', weight: 4, opacity: 0.8, pane: 'customOverlayPane'}).addTo(pathPlanLayer);
                }
            }
            
            var tempData = getJsonFromId('json_temp_clicks');
            if (tempData) {
                tempLayer.clearLayers();
                if (tempData.clicks) {
                    var pts = tempData.clicks.map(c => [c.y, c.x]);
                    tempData.clicks.forEach((c, idx) => { L.circleMarker([c.y, c.x], { radius: 6, color: '#FF8C00', fillColor: '#FFA500', fillOpacity: 1.0, pane: 'customOverlayPane' }).bindTooltip((idx+1).toString(), {permanent: true, direction: "center"}).addTo(tempLayer); });
                    if (pts.length > 1) { L.polyline(pts, {color: "#FFA500", weight: 3, dashArray: "5, 5", pane: 'customOverlayPane'}).addTo(tempLayer); }
                }
            }

            var areaData = getJsonFromId('json_areas');
            if (areaData && areaData.visible) {
                if (!map.hasLayer(areaLayer)) map.addLayer(areaLayer); areaLayer.clearLayers(); 
                if (areaData.areas) {
                    areaData.areas.forEach(function(item) {
                        var start = item.area.start; var end = item.area.end; var half_width = item.area.half_width;
                        var color = areaColors[item.type] || areaColors['default'];
                        var corners = getRectCorners(start, end, half_width);
                        if (corners) {
                            L.polygon(corners, { color: color, weight: 2, fillOpacity: 0.4, fillColor: color, pane: 'customAreaPane', interactive: true })
                             .bindTooltip(item.type, {sticky: false, direction: "top"})
                             .addTo(areaLayer);
                             
                            if (item.type === 'forbidden_area' && item.metadata && item.metadata.escape_distance) {
                                var dist = parseFloat(item.metadata.escape_distance);
                                if (dist > 0) {
                                    var innerCorners = getInnerRectCorners(start, end, half_width, dist);
                                    if (innerCorners) {
                                        L.polygon(innerCorners, {color: '#FFFFFF', weight: 1, dashArray: '4, 4', fill: false, pane: 'customAreaPane', interactive: false}).addTo(areaLayer);
                                    }
                                }
                            }

                            if (item.type === 'elevator_area') {
                                var doorType = "0";
                                if (item.metadata && item.metadata.elevator_door_type) { doorType = item.metadata.elevator_door_type; }
                                var schedDist = 1.0;
                                if (item.metadata && item.metadata.elevator_scheduling_point_dist) { schedDist = parseFloat(item.metadata.elevator_scheduling_point_dist); }
                                
                                var doorDepth = 0.2; 
                                var dx = end.x - start.x; var dy = end.y - start.y; var len = Math.sqrt(dx*dx + dy*dy);
                                var ux = dx / len; var uy = dy / len; 
                                
                                var drawSide = function(dir, label) {
                                    var dCorners = getDoorCorners(start, end, half_width, doorDepth, dir);
                                    if (dCorners) L.polygon(dCorners, {color: '#00008B', weight: 2, fillOpacity: 0.8, fillColor: '#00008B', pane: 'customAreaPane', interactive: false}).addTo(areaLayer);
                                    
                                    var base = (dir === 1) ? start : end; 
                                    var sign = (dir === 1) ? -1 : 1; 
                                    var px = base.x + ux * sign * schedDist; 
                                    var py = base.y + uy * sign * schedDist;
                                    
                                    L.marker([py, px], {icon: bluePinIcon, pane: 'customOverlayPane'}).bindTooltip(label, {direction: "top", offset: [0, -24], sticky: false}).addTo(areaLayer);
                                };
                                
                                if (doorType == "0" || doorType == "2") drawSide(1, "Front");
                                if (doorType == "1" || doorType == "2") drawSide(-1, "Rear");
                            }
                        }
                    });
                }
            } else { if (map.hasLayer(areaLayer)) map.removeLayer(areaLayer); }

            var lineData = getJsonFromId('json_lines');
            if (lineData && lineData.visible) {
                if (!map.hasLayer(lineLayer)) map.addLayer(lineLayer); lineLayer.clearLayers();
                if (lineData.lines) {
                    lineData.lines.forEach(function(item) {
                        var l = item.line; var type = item.type; var style = lineStyles[type] || {color: 'black', pane: 'customLinePane'};
                        var start = [l.start.y, l.start.x]; var end = [l.end.y, l.end.x];
                        L.polyline([start, end], style).addTo(lineLayer);
                    });
                }
                if(lineLayer.getLayers().length > 0) lineLayer.bringToFront();
            } else { if (map.hasLayer(lineLayer)) map.removeLayer(lineLayer); }
        }

        function drawRobot(x, y, yaw, name, isSelected) {
            var len = 0.74; var wid = 0.44;
            var bodyCornersRel = [[ len/2,  wid/2], [-len/2,  wid/2], [-len/2, -wid/2], [ len/2, -wid/2]];
            var tSize = 0.25; var triPointsRel = [[ tSize, 0], [-tSize/2,  tSize/1.5], [-tSize/2, -tSize/1.5]];
            function transform(points) {
                return points.map(p => {
                    var rx = p[0]; var ry = p[1];
                    var rotX = rx * Math.cos(yaw) - ry * Math.sin(yaw);
                    var rotY = rx * Math.sin(yaw) + ry * Math.cos(yaw);
                    return [y + rotY, x + rotX];
                });
            }
            var bodyCoords = transform(bodyCornersRel); var triCoords = transform(triPointsRel);
            var bodyColor = isSelected ? '#0000FF' : '#5555FF'; 
            var body = L.polygon(bodyCoords, { color: 'black', weight: 1, fillColor: bodyColor, fillOpacity: 0.4, interactive: true, pane: 'customRobotPane' });
            body.bindTooltip(name, {permanent: false, direction: "top", offset: [0, -10]});
            var head = L.polygon(triCoords, { color: 'black', weight: 1, fillColor: '#FF0000', fillOpacity: 1.0, interactive: false, pane: 'customRobotPane' });
            return [body, head];
        }
        var style = document.createElement('style');
        style.innerHTML = '.path-label { background: transparent; border: none; box-shadow: none; color: black; font-weight: bold; font-size: 10px; }';
        document.getElementsByTagName('head')[0].appendChild(style);
        setInterval(updateAllLayers, 200);
        {% endmacro %}
        """)
    
    def render(self, **kwargs):
        return super(MSISManager, self).render(**kwargs)

def get_map_view(robot_name, manager):
    if not robot_name:
        all_robots = manager.get_all_robots()
        target_robot = list(all_robots.values())[0] if all_robots else None
    else:
        target_robot = manager.get_robot(robot_name)
    if not target_robot or not target_robot.connected: return "<div>Robot Offline</div>"
    content = target_robot.get_map_explore()
    if not content: return "<div>Map Offline</div>"
    grid, meta = parse_grid_and_meta(content)
    img_b64 = generate_map_base64(grid)
    bounds = [[meta['min_y'], meta['min_x']], [meta['max_y'], meta['max_x']]]
    center_y = (meta['min_y'] + meta['max_y']) / 2
    center_x = (meta['min_x'] + meta['max_x']) / 2
    m = folium.Map(location=[center_y, center_x], zoom_start=3, crs="Simple", tiles=None, zoom_control=True, zoom_snap=0.1, zoom_delta=0.1, attr='MSIS AMR', attribution_control=False)
    m.get_root().header.add_child(folium.Element("<style>body, .folium-map { background-color: #808080 !important; }</style>"))
    m.get_root().html.add_child(folium.Element(f"<script>window.mapBounds = {bounds}; window.mapData = {{ url: '{img_b64}', bounds: {bounds} }};</script>"))
    m.add_child(MSISManager())
    return m._repr_html_()