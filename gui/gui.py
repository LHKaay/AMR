# gui/gui.py
import gradio as gr
from . import gui_utils

custom_css = """
.gradio-container { max-width: 100% !important; padding: 0 !important; margin: 0 !important; background-color: #808080 !important; }
body { margin: 0; padding: 0; background-color: #808080 !important; }
footer { display: none !important; }
.leaflet-control-attribution { display: none !important; }
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
.btn_go_poi { background-color: #212121 !important; color: white !important; }
.btn-primary-custom { background-color: #2196F3 !important; color: white !important; }
.dpad-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; width: 180px; margin: 10px auto; }
iframe { height: 93vh !important; width: 100% !important; border: none !important; background-color: #808080 !important; }
"""

js_loader = """function() { console.log("UI Loaded"); }"""

def create_gui():
    robot_names = gui_utils.get_robot_list()
    init_val = robot_names[0] if robot_names else None

    with gr.Blocks(title="MSIS Control Studio") as demo:
        # State Variables
        waypoint_state = gr.State([]) 
        poi_state = gr.State([]) # Stores full dict list [{'name':.., 'x':.., 'y':.., 'yaw':..}]

        with gr.Row(elem_id="top_menu"):
            btn_menu_motion = gr.Button("Motion", elem_classes="menu_btn")
            btn_menu_map = gr.Button("MAP", elem_classes="menu_btn")
            btn_menu_arm = gr.Button("ARM", elem_classes="menu_btn")
            btn_menu_cam = gr.Button("CAMERA", elem_classes="menu_btn")

        with gr.Row():
            with gr.Sidebar(elem_id="sidebar", width=350):
                gr.HTML(gui_utils.get_logo_html("logo/MSIS_WB_logo.png"))
                gr.Markdown("## 🤖 MSIS Manager", elem_classes=["section-header"])
                robot_dropdown = gr.Dropdown(choices=robot_names, value=init_val, label="Select Target Robot")
                
                with gr.Accordion("➕ Add Robot", open=False):
                    with gr.Row():
                        txt_name = gr.Textbox(label="Name", placeholder="AMR_01", value="AMR_0")
                        txt_ip = gr.Textbox(label="IP", placeholder="192.168.0.x", value="192.168.0.")
                    btn_add_robot = gr.Button("Add", elem_classes=["btn-primary-custom"])
                    msg_box = gr.Markdown("")

                with gr.Row():
                    status_display = gr.Markdown("🔋 Status: Checking...")

                # --- Motion Sidebar ---
                with gr.Column(visible=False) as grp_motion:
                    gr.Markdown("🚀 **Motion Planning**", elem_classes=["section-header"])
                    click_mode = gr.Radio(["info", "add_point"], label="Map Click Mode", value="info")
                    target_display = gr.Textbox(label="Last Clicked", interactive=False)
                    waypoint_log = gr.TextArea(label="Waypoint List", interactive=False, lines=5)
                    with gr.Row():
                        btn_clear_path = gr.Button("🗑️ Clear List", variant="secondary")
                    gr.Markdown("### 🎮 Execute")
                    with gr.Row():
                        btn_run_path = gr.Button("▶️ Run Path (Seq)", elem_classes=["btn-primary-custom"])
                    with gr.Row():
                        btn_run_ortho = gr.Button("📐 Ortho Move (Last Pt)")
                    motion_msg = gr.Markdown("")

                # --- MAP Sidebar ---
                with gr.Column(visible=True) as grp_map: 
                    
                    pose_display = gr.Markdown("Position: ...")
                    # Manual Control
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
                    
                    # ---------------------------
                    # POI Manager Section (New)
                    # ---------------------------
                    gr.Markdown("📍 **POI Manager**", elem_classes=["section-header"])
                    
                    # 1. Creation Area
                    with gr.Row():
                        txt_new_poi_name = gr.Textbox(show_label=False, placeholder="New POI Name", scale=2)
                    with gr.Row():
                        btn_add_click = gr.Button("Add from Click", scale=1)
                        btn_add_robot_pose = gr.Button("Add from Robot", scale=1)

                    # 2. Management Area (List & Edit)
                    gr.Markdown("📋 **Saved POIs**")
                    # Dataframe 대신 Dropdown 사용
                    dd_poi_list = gr.Dropdown(label="Select POI", choices=[], interactive=True)
                    
                    with gr.Row():
                        in_edit_name = gr.Textbox(label="Name", interactive=True)
                    with gr.Row():
                        in_edit_x = gr.Number(label="X", interactive=True)
                        in_edit_y = gr.Number(label="Y", interactive=True)
                        in_edit_yaw = gr.Number(label="Yaw", interactive=True)
                        
                    with gr.Row():
                        btn_go_poi = gr.Button("🚀 GO", elem_classes=["btn_go_poi"])
                        btn_update_poi = gr.Button("💾 Update")
                        btn_delete_poi = gr.Button("🗑️ Delete")

                    with gr.Row():
                        btn_save_csv = gr.Button("Export CSV")
                        btn_load_csv = gr.UploadButton("Import CSV", file_types=[".csv"])
                        btn_clear_all_poi = gr.Button("Clear All")
                    
                    poi_file_out = gr.File(label="Download", visible=False)
                    poi_msg = gr.Markdown("", visible=True)


            with gr.Column(elem_id="map-container"):
                map_html = gr.HTML(value=gui_utils.get_map_view(init_val))
                json_pose = gr.Textbox(elem_id="json_pose", visible=True, elem_classes=["hidden-elem"])
                json_lidar = gr.Textbox(elem_id="json_lidar", visible=True, elem_classes=["hidden-elem"])
                json_map = gr.Textbox(elem_id="json_map", visible=True, elem_classes=["hidden-elem"])
                target_coords_json = gr.Textbox(elem_id="target_coords_json", visible=True, elem_classes=["hidden-elem"])

        # --- Events Wiring ---
        
        def change_tab(tab):
            m, mp = gui_utils.toggle_sidebar(tab)
            return gr.update(visible=m), gr.update(visible=mp)

        btn_menu_motion.click(lambda: change_tab("Motion"), None, [grp_motion, grp_map])
        btn_menu_map.click(lambda: change_tab("MAP"), None, [grp_motion, grp_map])

        target_coords_json.change(
            gui_utils.handle_map_click, 
            inputs=[target_coords_json, waypoint_state, click_mode], 
            outputs=[target_display, waypoint_state, waypoint_log]
        )

        # [POI Events]
        # 1. Add POIs (Update State & Dropdown choices)
        btn_add_click.click(
            gui_utils.add_poi_from_click,
            inputs=[txt_new_poi_name, target_coords_json, poi_state],
            outputs=[poi_state, dd_poi_list, poi_msg]
        )
        btn_add_robot_pose.click(
            gui_utils.add_poi_from_robot,
            inputs=[txt_new_poi_name, robot_dropdown, poi_state],
            outputs=[poi_state, dd_poi_list, poi_msg]
        )

        # 2. Select POI -> Fill Inputs
        dd_poi_list.change(
            gui_utils.get_poi_details,
            inputs=[dd_poi_list, poi_state],
            outputs=[in_edit_name, in_edit_x, in_edit_y, in_edit_yaw]
        )

        # 3. Actions (Go, Update, Delete)
        btn_go_poi.click(
            gui_utils.go_to_poi_action,
            inputs=[robot_dropdown, dd_poi_list, poi_state],
            outputs=[poi_msg]
        )
        btn_update_poi.click(
            gui_utils.update_poi_data,
            inputs=[dd_poi_list, in_edit_name, in_edit_x, in_edit_y, in_edit_yaw, poi_state],
            outputs=[poi_state, dd_poi_list, poi_msg]
        )
        btn_delete_poi.click(
            gui_utils.delete_selected_poi,
            inputs=[dd_poi_list, poi_state],
            outputs=[poi_state, dd_poi_list, poi_msg]
        )
        
        # 4. CSV & Clear
        btn_save_csv.click(gui_utils.export_pois_to_csv, poi_state, poi_file_out).then(lambda: gr.update(visible=True), None, poi_file_out)
        btn_load_csv.upload(gui_utils.import_pois_from_csv, btn_load_csv, [poi_state, dd_poi_list])
        
        # Clear All -> Update State & Dropdown
        def clear_all_wrapper():
            return [], gr.update(choices=[], value=None)
        btn_clear_all_poi.click(clear_all_wrapper, None, [poi_state, dd_poi_list])


        # Robot & Motion Controls
        def add_robot_wrapper(n, i):
            new_list = gui_utils.add_new_robot(n, i)
            return gr.update(choices=new_list, value=n), f"Added {n}"
        
        btn_add_robot.click(add_robot_wrapper, [txt_name, txt_ip], [robot_dropdown, msg_box])
        btn_clear_path.click(gui_utils.clear_waypoints, None, [waypoint_state, waypoint_log])
        btn_run_path.click(lambda n, w: gui_utils.trigger_motion(n, w, "path"), [robot_dropdown, waypoint_state], [motion_msg])
        btn_run_ortho.click(lambda n, w: gui_utils.trigger_motion(n, w, "ortho"), [robot_dropdown, waypoint_state], [motion_msg])
        
        btn_up.click(lambda r: gui_utils.manual_move(r, 0), [robot_dropdown], None)
        btn_down.click(lambda r: gui_utils.manual_move(r, 1), [robot_dropdown], None)
        btn_left.click(lambda r: gui_utils.manual_move(r, 3), [robot_dropdown], None)
        btn_right.click(lambda r: gui_utils.manual_move(r, 2), [robot_dropdown], None)
        btn_stop.click(gui_utils.cmd_stop, [robot_dropdown], None)

        timer = gr.Timer(value=0.1)
        timer.tick(
            gui_utils.update_all_loop,
            inputs=[robot_dropdown, chk_map, chk_laser, chk_robot, chk_axis, poi_state],
            outputs=[json_pose, json_lidar, json_map, pose_display, status_display]
        )
        
        demo.load(None, None, None, js=js_loader)
        return demo