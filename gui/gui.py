import gradio as gr
import json
import csv
from . import gui_map_utils
from .msis_amr import manager

custom_css = """
.gradio-container { max-width: 100% !important; padding: 0 !important; margin: 0 !important; background-color: #808080 !important; }
body { margin: 0; padding: 0; background-color: #808080 !important; }
footer { display: none !important; }
.leaflet-control-attribution { display: none !important; }
.hidden-elem { display: none !important; }
#top_menu { background-color: #424242 !important; color: #FFFFFF !important; padding: 10px 25px; border-bottom: none; }
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

/* 탭 헤더 숨기기 */
#sidebar_tabs > .tab-nav { display: none !important; }
"""

js_loader = """function() { console.log("UI Loaded"); }"""

# --- Helper Functions ---
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
    except: return "Error", waypoint_list, ""

def get_poi_names(poi_list):
    return [p['name'] for p in poi_list] if poi_list else []

def add_poi_click(name, json_str, current):
    if not json_str: return current, gr.update(choices=get_poi_names(current)), "Click map first"
    try:
        c = json.loads(json_str)
        new_name = name if name else f"POI_{len(current)+1}"
        current.append({"name": new_name, "x": c['x'], "y": c['y'], "yaw": 0})
        return current, gr.update(choices=get_poi_names(current), value=new_name), "Added"
    except: return current, gr.update(), "Error"

def add_poi_robot(name, r_name, current):
    r = manager.get_robot(r_name)
    if r and (p := r.get_pose()):
        new_name = name if name else f"Robot_{len(current)+1}"
        current.append({"name": new_name, "x": p['x'], "y": p['y'], "yaw": p['yaw']})
        return current, gr.update(choices=get_poi_names(current), value=new_name), "Added"
    return current, gr.update(), "Error"

def delete_poi(name, current):
    updated = [p for p in current if p['name'] != name]
    return updated, gr.update(choices=get_poi_names(updated), value=None), "Deleted"

def update_poi(name, new_name, x, y, yaw, current):
    updated = []
    for p in current:
        if p['name'] == name: updated.append({"name": new_name, "x": x, "y": y, "yaw": yaw})
        else: updated.append(p)
    return updated, gr.update(choices=get_poi_names(updated), value=new_name), "Updated"

def go_poi(r_name, p_name, current):
    target = next((p for p in current if p['name'] == p_name), None)
    if target:
        manager.get_robot(r_name).move_to(target['x'], target['y'])
        return f"Moving to {p_name}"
    return "POI Not Found"

def poi_details(name, current):
    t = next((p for p in current if p['name'] == name), None)
    return (t['name'], t['x'], t['y'], t['yaw']) if t else ("",0,0,0)

def export_csv(current):
    if not current: return None
    with open("POI.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["x", "y", "yaw", "name"])
        for p in current: writer.writerow([p['x'], p['y'], p.get('yaw',0), p['name']])
    return "POI.csv"

def import_csv(file_obj):
    if not file_obj: return [], gr.update()
    new_pois = []
    try:
        with open(file_obj.name, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                new_pois.append({"x": float(r['x']), "y": float(r['y']), "yaw": float(r.get('yaw',0)), "name": r['name']})
        return new_pois, gr.update(choices=get_poi_names(new_pois), value=None)
    except: return [], gr.update()

def clear_all_pois(): return [], gr.update(choices=[], value=None)

# --------------------------
# Main GUI Creation
# --------------------------
def create_gui():
    robot_names = manager.get_robot_names()
    init_val = robot_names[0] if robot_names else None

    with gr.Blocks(title="MSIS Control Studio") as demo:
        waypoint_state = gr.State([]) 
        poi_state = gr.State([]) 

        # --- Top Menu ---
        with gr.Row(elem_id="top_menu"):
            btn_menu_motion = gr.Button("Motion", elem_classes="menu_btn")
            btn_menu_map = gr.Button("MAP", elem_classes="menu_btn")
            btn_menu_arm = gr.Button("ARM", elem_classes="menu_btn")
            btn_menu_cam = gr.Button("CAMERA", elem_classes="menu_btn")

        with gr.Row():
            # --- Sidebar ---
            with gr.Sidebar(elem_id="sidebar", width=350):
                gr.HTML(gui_map_utils.get_logo_html("logo/MSIS_WB_logo.png"))
                gr.Markdown("## 🤖 MSIS Manager", elem_classes=["section-header"])
                
                # 로봇 선택 및 추가
                robot_dropdown = gr.Dropdown(choices=robot_names, value=init_val, label="Select Target Robot")
                
                with gr.Accordion("➕ Add Robot", open=False):
                    with gr.Row():
                        txt_name = gr.Textbox(label="Name", placeholder="AMR_01", value="AMR_0")
                        txt_ip = gr.Textbox(label="IP", placeholder="192.168.0.x", value="192.168.0.")
                    btn_add_robot = gr.Button("Add", elem_classes=["btn-primary-custom"])
                    msg_box = gr.Markdown("")

                with gr.Row():
                    status_display = gr.Markdown("🔋 Status: Checking...")

                # --- Tabs for Menu Switching ---
                # [수정] gr.Tabs를 사용하여 메뉴 전환 구현 (버튼 클릭 시 selected 업데이트)
                with gr.Tabs(elem_id="sidebar_tabs") as sidebar_tabs:
                    
                    # Tab 1: Motion
                    with gr.Tab("Motion", id="Motion"):
                        gr.Markdown("🚀 **Motion Planning**", elem_classes=["section-header"])
                        click_mode = gr.Radio(["info", "add_point"], label="Map Click Mode", value="info")
                        target_display = gr.Textbox(label="Last Clicked", interactive=False)
                        waypoint_log = gr.TextArea(label="Waypoint List", interactive=False, lines=5)
                        btn_clear_path = gr.Button("🗑️ Clear List", variant="secondary")
                        gr.Markdown("### 🎮 Execute")
                        with gr.Row():
                            btn_run_path = gr.Button("▶️ Run Path", elem_classes=["btn-primary-custom"])
                            btn_run_ortho = gr.Button("📐 Ortho Move")
                        motion_msg = gr.Markdown("")

                    # Tab 2: MAP (기본 선택)
                    with gr.Tab("MAP", id="MAP"): 
                        pose_display = gr.Markdown("Position: ...")
                        
                        gr.Markdown("🎮 Manual Control", elem_classes=["section-header"])
                        with gr.Column(elem_classes="dpad-grid"):
                            gr.HTML("<div></div>"); btn_up = gr.Button("▲", elem_classes=["btn-nav"]); gr.HTML("<div></div>")
                            btn_left = gr.Button("◀", elem_classes=["btn-nav"]); btn_stop = gr.Button("STOP", elem_classes=["btn-stop"]); btn_right = gr.Button("▶", elem_classes=["btn-nav"])
                            gr.HTML("<div></div>"); btn_down = gr.Button("▼", elem_classes=["btn-nav"]); gr.HTML("<div></div>")

                        gr.Markdown("👁️ Layers", elem_classes=["section-header"])
                        with gr.Row():
                            chk_map = gr.Checkbox(label="Map", value=True)
                            chk_laser = gr.Checkbox(label="Laser", value=True)
                        with gr.Row():
                            chk_robot = gr.Checkbox(label="Robot", value=True)
                            chk_axis = gr.Checkbox(label="Axis", value=False)
                        
                        gr.Markdown("📍 **POI Manager**", elem_classes=["section-header"])
                        with gr.Row():
                            txt_new_poi_name = gr.Textbox(show_label=False, placeholder="New POI Name", scale=2)
                        with gr.Row():
                            btn_add_click = gr.Button("Add from Click", scale=1)
                            btn_add_robot_pose = gr.Button("Add from Robot", scale=1)

                        gr.Markdown("📋 **Saved POIs**")
                        dd_poi_list = gr.Dropdown(label="Select POI", choices=[], interactive=True)
                        with gr.Row():
                            in_edit_name = gr.Textbox(label="Name", interactive=True)
                        with gr.Row():
                            in_edit_x = gr.Number(label="X", interactive=True)
                            in_edit_y = gr.Number(label="Y", interactive=True)
                            in_edit_yaw = gr.Number(label="Yaw", interactive=True)
                        with gr.Row():
                            btn_go_poi = gr.Button("🚀 GO", variant="primary")
                            btn_update_poi = gr.Button("💾 Update")
                            btn_delete_poi = gr.Button("🗑️ Delete", variant="stop")
                        with gr.Row():
                            btn_save_csv = gr.Button("Export CSV")
                            btn_load_csv = gr.UploadButton("Import CSV", file_types=[".csv"])
                            btn_clear_all_poi = gr.Button("Clear All")
                        poi_file_out = gr.File(label="Download", visible=False)
                        poi_msg = gr.Markdown("", visible=True)

            # --- Map Area ---
            with gr.Column(elem_id="map-container"):
                map_html = gr.HTML(value=gui_map_utils.get_map_view(init_val, manager))
                json_pose = gr.Textbox(elem_id="json_pose", visible=True, elem_classes=["hidden-elem"])
                json_lidar = gr.Textbox(elem_id="json_lidar", visible=True, elem_classes=["hidden-elem"])
                json_map = gr.Textbox(elem_id="json_map", visible=True, elem_classes=["hidden-elem"])
                target_coords_json = gr.Textbox(elem_id="target_coords_json", visible=True, elem_classes=["hidden-elem"])

        # --- Events Wiring ---
        
        # [Fix 1] Tab Switching Logic: Return gr.update(selected=...)
        btn_menu_motion.click(fn=lambda: gr.update(selected="Motion"), inputs=None, outputs=sidebar_tabs)
        btn_menu_map.click(fn=lambda: gr.update(selected="MAP"), inputs=None, outputs=sidebar_tabs)
        
        # [Fix 2] Refresh Map when Robot Changes
        def refresh_map(r_name):
            return gui_map_utils.get_map_view(r_name, manager)
        robot_dropdown.change(refresh_map, robot_dropdown, map_html)

        # Map Click
        target_coords_json.change(handle_map_click, [target_coords_json, waypoint_state, click_mode], [target_display, waypoint_state, waypoint_log])

        # POI Logic
        btn_add_click.click(add_poi_click, [txt_new_poi_name, target_coords_json, poi_state], [poi_state, dd_poi_list, poi_msg])
        btn_add_robot_pose.click(add_poi_robot, [txt_new_poi_name, robot_dropdown, poi_state], [poi_state, dd_poi_list, poi_msg])
        dd_poi_list.change(poi_details, [dd_poi_list, poi_state], [in_edit_name, in_edit_x, in_edit_y, in_edit_yaw])
        btn_go_poi.click(go_poi, [robot_dropdown, dd_poi_list, poi_state], [poi_msg])
        btn_update_poi.click(update_poi, [dd_poi_list, in_edit_name, in_edit_x, in_edit_y, in_edit_yaw, poi_state], [poi_state, dd_poi_list, poi_msg])
        btn_delete_poi.click(delete_poi, [dd_poi_list, poi_state], [poi_state, dd_poi_list, poi_msg])
        btn_save_csv.click(export_csv, poi_state, poi_file_out).then(lambda: gr.update(visible=True), None, poi_file_out)
        btn_load_csv.upload(import_csv, btn_load_csv, [poi_state, dd_poi_list])
        btn_clear_all_poi.click(clear_all_pois, None, [poi_state, dd_poi_list])

        # Robot Management (Add & Update Dropdown & Update Map)
        def add_robot_wrapper(n, i):
            new_list = manager.add_robot(n, i)
            # 로봇 추가 후 맵도 갱신
            new_map = gui_map_utils.get_map_view(n, manager)
            return gr.update(choices=new_list, value=n), new_map, f"Added {n}"
        
        btn_add_robot.click(add_robot_wrapper, [txt_name, txt_ip], [robot_dropdown, map_html, msg_box])

        # Motion Control
        btn_clear_path.click(lambda: ([], ""), None, [waypoint_state, waypoint_log])
        btn_run_path.click(lambda n, w: manager.trigger_motion_thread(n, w, "path"), [robot_dropdown, waypoint_state], [motion_msg])
        btn_run_ortho.click(lambda n, w: manager.trigger_motion_thread(n, w, "ortho"), [robot_dropdown, waypoint_state], [motion_msg])
        
        btn_up.click(lambda r: manager.manual_move(r, 0), [robot_dropdown], None)
        btn_down.click(lambda r: manager.manual_move(r, 1), [robot_dropdown], None)
        btn_left.click(lambda r: manager.manual_move(r, 3), [robot_dropdown], None)
        btn_right.click(lambda r: manager.manual_move(r, 2), [robot_dropdown], None)
        btn_stop.click(manager.cmd_stop, [robot_dropdown], None)

        # Data Update Loop
        timer = gr.Timer(value=0.2)
        timer.tick(
            manager.update_data_for_ui,
            inputs=[robot_dropdown, chk_map, chk_laser, chk_robot, chk_axis, poi_state],
            outputs=[json_pose, json_lidar, json_map, pose_display, status_display]
        )
        
        demo.load(None, None, None, js=js_loader)
        return demo