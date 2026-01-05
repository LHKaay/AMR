import gradio as gr
import json
from . import gui_map_utils
from .msis_amr import manager
from . import gui_handlers as gh 

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
.btn-primary-custom { background-color: #2196F3 !important; color: white !important; }
.dpad-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; width: 180px; margin: 10px auto; }
iframe { height: 93vh !important; width: 100% !important; border: none !important; background-color: #808080 !important; }
#sidebar_tabs > .tab-nav { display: none !important; }
"""

js_loader = """function() { console.log("UI Loaded"); }"""

def create_gui():
    robot_names = manager.get_robot_names()
    init_val = robot_names[0] if robot_names else None

    with gr.Blocks(title="MSIS Control Studio") as demo:
        poi_state = gr.State([])
        click_state = gr.State([])      
        ui_mode = gr.State(gh.MODE_NAV)    
        last_click_coords = gr.State(None)
        st_selected_area = gr.State(None)
        
        st_pose = gr.State("📍 Pose: Checking...")
        st_status = gr.State("🤖 Status: Checking...")
        st_health = gr.State("Checking...")
        st_target = gr.State("🎯 Target: None")
        st_temp_points = gr.State([])

        json_areas = gr.Textbox(label="Area Data", visible=True, elem_id="json_areas", elem_classes=["hidden-elem"])
        json_lines = gr.Textbox(label="Line Data", visible=True, elem_id="json_lines", elem_classes=["hidden-elem"])
        json_temp_clicks = gr.Textbox(label="Temp Clicks", visible=False, elem_id="json_temp_clicks", elem_classes=["hidden-elem"])
        
        with gr.Row(elem_id="top_menu"):
            btn_menu_motion = gr.Button("Motion", elem_classes="menu_btn")
            btn_menu_map = gr.Button("MAP", elem_classes="menu_btn")
            btn_menu_arm = gr.Button("ARM", elem_classes="menu_btn")
            btn_menu_cam = gr.Button("CAMERA", elem_classes="menu_btn")

        with gr.Row():
            with gr.Sidebar(elem_id="sidebar", width=320):
                gr.HTML(gui_map_utils.get_logo_html("map_icon/MSIS_WB_logo.png"))
                gr.Markdown("## 🤖 MSIS AMMR", elem_classes=["section-header"])
                robot_dropdown = gr.Dropdown(choices=robot_names, value=init_val, label="Target Robot")
                
                with gr.Accordion("🔌 Power & Dock", open=False):
                        btn_shutdown = gr.Button("🛑 Shutdown Robot", variant="stop")
                        gr.Markdown("**Home Dock Manager**")
                        with gr.Row():
                            txt_dock_name = gr.Textbox(show_label=False, placeholder="Dock Name")
                            btn_reg_dock = gr.Button("Set Current Pose as Dock")
                        
                        btn_go_home = gr.Button("🏠 Go Dock", variant="primary") 
                        
                        dd_dock_list = gr.Dropdown(label="Existing Docks", choices=[])
                        with gr.Row():
                            btn_refresh_dock = gr.Button("🔄 Refresh")
                            btn_del_dock = gr.Button("🗑️ Delete")

                with gr.Accordion("➕ Add Robot", open=False):
                    with gr.Row():
                        txt_name = gr.Textbox(label="Name", placeholder="AMR_01", value="AMR_0")
                        txt_ip = gr.Textbox(label="IP", placeholder="192.168.0.x", value="192.168.0.")
                    btn_add_robot = gr.Button("Add", elem_classes=["btn-primary-custom"])
                
                with gr.Accordion("🛠️ Calibration", open=False):
                    gr.Markdown("Align robot orientation axis manually.")
                    btn_align_axis = gr.Button("🧭 Set Current Heading to 0 (North)", variant="secondary")

                mode_status_msg = gr.Markdown("### Mode: Navigation")
                gr.Markdown("---")

                with gr.Tab("🚀 Motion"):
                    motion_msg = gr.Textbox(label="Result", lines=2, interactive=False)
                    gr.Markdown("### 📍 Single Point Navigation")
                    txt_nav_target = gr.Textbox(show_label=False, interactive=False, placeholder="Click map...")
                    btn_move_free = gr.Button("Move")
                    
                    gr.Markdown("**1. Navigation on Track**")
                    txt_track_target_motion = gr.Textbox(show_label=False,interactive=False, placeholder="Click map...")
                    dd_track_mode = gr.Dropdown(choices=gh.TRACK_MOVE_MODES, value=2, label="Track Mode")
                    btn_follow_track = gr.Button("Follow Track")

                with gr.Tab("Artifacts"):
                    txt_dashboard = gr.Textbox(label="Robot Dashboard", value="...", lines=6, interactive=False, elem_id="dashboard_box")
                    btn_clear_error = gr.Button("⚠️ Clear Error", visible=False, variant="stop")
                    
                    gr.Markdown("🎮 Manual Control", elem_classes=["section-header"])
                    with gr.Column(elem_classes="dpad-grid"):
                        gr.HTML("<div></div>"); btn_up = gr.Button("▲", elem_classes=["btn-nav"]); gr.HTML("<div></div>")
                        btn_left = gr.Button("◀", elem_classes=["btn-nav"]); btn_stop = gr.Button("STOP", elem_classes=["btn-stop"]); btn_right = gr.Button("▶", elem_classes=["btn-nav"])
                        gr.HTML("<div></div>"); btn_down = gr.Button("▼", elem_classes=["btn-nav"]); gr.HTML("<div></div>")

                    gr.Markdown("Layers", elem_classes=["section-header"])
                    with gr.Row():
                        chk_map = gr.Checkbox(label="Map", value=True)
                        chk_robot = gr.Checkbox(label="Robot", value=True)
                        chk_axis = gr.Checkbox(label="Axis", value=False)
                    with gr.Row():
                        chk_lidar_rays = gr.Checkbox(label="Lidar Rays", value=False)
                        chk_lidar_points = gr.Checkbox(label="Lidar Points", value=False)
                    with gr.Row():
                        chk_path = gr.Checkbox(label="Path Plan", value=False)
                        chk_traj = gr.Checkbox(label="Trajectory", value=False)

                    with gr.Accordion("Line (Wall/Track)", open=False):
                        line_type = gr.Dropdown(choices=gh.ARTIFACT_TYPES, value="walls", label="Type")
                        with gr.Row():
                            btn_start_draw_line = gr.Button("— Line (2 Pts)")
                            btn_start_draw_rect = gr.Button("🟥 Rect Line (2 Pts)")
                            btn_start_draw_curve = gr.Button("〰️ Curve (Multi Pts)")
                        btn_finish_curve = gr.Button("✅ Finish Curve Drawing")
                        with gr.Row():
                            btn_get_lines = gr.Button("🔄 Load All Lines")
                            btn_del_type_lines = gr.Button("🗑️ Del All Type")
                            btn_del_line_at_click = gr.Button("❌ Del Line at Click")

                    with gr.Accordion("POI Manager", open=False):
                        with gr.Column():
                            with gr.Row():
                                dd_poi_api_list = gr.Dropdown(label="Select POI", choices=[], scale=2)
                                btn_refresh_poi = gr.Button("🔄", scale=1)
                            
                            with gr.Row():
                                txt_poi_edit_id = gr.Textbox(label="ID", visible=False)
                                txt_poi_edit_name = gr.Textbox(label="Name")
                                dd_poi_edit_type = gr.Dropdown(choices=["Generic", "Charge", "Rest", "ElevatorWait", "ElevatorIn", "ROOM", "PARKING", "REFILL"], value="Generic", label="Type", allow_custom_value=True)
                            
                            with gr.Row():
                                num_poi_x = gr.Number(label="X", precision=4)
                                num_poi_y = gr.Number(label="Y", precision=4)
                                num_poi_yaw = gr.Number(label="Yaw", precision=4)
                            
                            with gr.Row():
                                btn_add_poi_robot = gr.Button("➕ At Robot")
                                btn_add_poi_click = gr.Button("➕ At Click")
                                btn_save_poi = gr.Button("💾 Update")
                            with gr.Row():
                                btn_del_poi_api = gr.Button("🗑️ Delete")
                                btn_adjust_poi = gr.Button("🔧 Adjust")

                    with gr.Accordion("Area", open=False):
                        area_type = gr.Dropdown(choices=gh.AREA_TYPES, value="forbidden_area", label="Type")
                        
                        dd_door_type = gr.Dropdown(choices=["Front Door", "Rear Door", "Double Doors"], value="Front Door", label="Elevator Door Type", visible=False)
                        
                        with gr.Column(visible=False) as group_dangerous:
                            dd_danger_type = gr.Dropdown(choices=["Slope", "Narrow"], value="Narrow", label="Danger Type")
                            slid_speed = gr.Slider(minimum=0.1, maximum=2.0, value=0.5, step=0.1, label="Max Speed (m/s)")
                            
                        with gr.Column(visible=False) as group_sensor:
                            chk_sensors = gr.CheckboxGroup(choices=["Sonar", "Bumper", "Cliff", "Depth Camera", "TOF Cliff"], label="Disabled Sensors")

                        btn_start_draw_area = gr.Button("□ Draw Area (Click 2 points)") 
                        
                        gr.Markdown("---")
                        btn_edit_area = gr.Button("⚙️ Edit Selected Area (On Map)")
                        with gr.Column(visible=False) as area_edit_panel:
                            gr.Markdown("### Edit Area")
                            with gr.Row():
                                in_cx = gr.Number(label="Center X"); in_cy = gr.Number(label="Center Y")
                            with gr.Row():
                                in_len = gr.Number(label="Length"); in_wid = gr.Number(label="Width"); in_rot = gr.Number(label="Rotation (rad)")
                            btn_confirm_edit = gr.Button("✅ Save Edit", variant="primary")
                            btn_cancel_edit = gr.Button("❌ Cancel", variant="stop")

                        with gr.Row():
                            btn_get_areas = gr.Button("🔄 Load All areas"); btn_del_sel_area = gr.Button("❌ Delete Selected Area"); btn_del_areas = gr.Button("🗑️ Del All")
                            
                    action_result = gr.Textbox(label="Result", interactive=False)

            with gr.Column(scale=3, elem_id="map-container"):
                map_html = gr.HTML(value=gui_map_utils.get_map_view(init_val, manager))
                json_pose = gr.Textbox(elem_id="json_pose", visible=True, elem_classes=["hidden-elem"])
                json_lidar = gr.Textbox(elem_id="json_lidar", visible=True, elem_classes=["hidden-elem"])
                json_map = gr.Textbox(elem_id="json_map", visible=True, elem_classes=["hidden-elem"])
                target_coords_json = gr.Textbox(elem_id="target_coords_json", visible=True, elem_classes=["hidden-elem"])

        area_type.change(gh.on_area_type_change, inputs=[area_type], outputs=[dd_door_type, group_dangerous, group_sensor])
        
        target_coords_json.change(gh.master_map_click, 
                                inputs=[target_coords_json, ui_mode, click_state, robot_dropdown, area_type, line_type, 
                                        st_pose, st_status, st_health, 
                                        dd_door_type, dd_danger_type, slid_speed, chk_sensors], 
                                outputs=[last_click_coords, click_state, ui_mode, mode_status_msg, 
                                         txt_nav_target, txt_track_target_motion, st_target, txt_dashboard, 
                                         json_areas, json_lines, action_result, json_temp_clicks, 
                                         st_temp_points, st_status, st_selected_area, area_edit_panel,
                                         in_cx, in_cy, in_len, in_wid, in_rot])
        
        btn_edit_area.click(gh.on_edit_click, inputs=[robot_dropdown, st_selected_area], outputs=[area_type, dd_door_type, in_cx, in_cy, in_len, in_wid, in_rot, area_edit_panel, action_result])
        btn_confirm_edit.click(gh.on_confirm_area, inputs=[robot_dropdown, area_type, dd_door_type, in_cx, in_cy, in_len, in_wid, in_rot, dd_danger_type, slid_speed, chk_sensors, st_selected_area], outputs=[json_areas, action_result, json_temp_clicks, area_edit_panel, st_temp_points, st_selected_area])
        btn_cancel_edit.click(gh.on_cancel_area, inputs=None, outputs=[action_result, json_temp_clicks, area_edit_panel, st_temp_points, st_selected_area])
        
        btn_add_robot.click(gh.add_robot_wrapper, [txt_name, txt_ip], [robot_dropdown, map_html])
        robot_dropdown.change(gh.refresh_map, robot_dropdown, map_html)
        btn_clear_error.click(gh.on_clear_error, robot_dropdown, action_result)
        btn_shutdown.click(gh.on_shutdown, robot_dropdown, action_result)
        btn_align_axis.click(gh.on_set_axis_zero, robot_dropdown, action_result)

        # -- Motion --
        btn_move_free.click(gh.on_free_move, [robot_dropdown, last_click_coords], motion_msg)
        btn_follow_track.click(gh.on_track_move, [robot_dropdown, last_click_coords, dd_track_mode], action_result)
        
        # -- Manual Move --
        btn_up.click(lambda r: manager.manual_move(r, 0), [robot_dropdown], None)
        btn_down.click(lambda r: manager.manual_move(r, 1), [robot_dropdown], None)
        btn_left.click(lambda r: manager.manual_move(r, 3), [robot_dropdown], None)
        btn_right.click(lambda r: manager.manual_move(r, 2), [robot_dropdown], None)
        btn_stop.click(manager.cmd_stop, [robot_dropdown], None)
        
        # -- Areas -- #
        btn_get_areas.click(lambda n: json.dumps({"visible":True,"areas":manager.get_all_robot_areas(n)}), robot_dropdown, json_areas)
        btn_start_draw_area.click(gh.start_area_mode, None, [ui_mode, click_state, mode_status_msg])
        btn_del_sel_area.click(gh.on_delete_selected_area, [robot_dropdown, target_coords_json], [json_areas, action_result])
        btn_del_areas.click(gh.del_areas, [robot_dropdown, area_type], json_areas)
        
        # -- Lines -- #
        btn_get_lines.click(gh.on_get_lines, [robot_dropdown], [json_lines, action_result])
        btn_start_draw_line.click(gh.start_line_mode, None, [ui_mode, click_state, mode_status_msg])
        btn_start_draw_rect.click(gh.start_rect_line_mode, None, [ui_mode, click_state, mode_status_msg])
        btn_del_type_lines.click(gh.on_delete_type_lines, [robot_dropdown, line_type], [json_lines, action_result])
        btn_del_line_at_click.click(gh.on_delete_line_at_point, [robot_dropdown, line_type, target_coords_json], [json_lines, action_result])
        btn_start_draw_curve.click(gh.start_curve_mode, None, [ui_mode, click_state, mode_status_msg])
        btn_finish_curve.click(gh.on_finish_curve, [robot_dropdown, line_type, click_state], [json_lines, action_result, click_state, ui_mode, mode_status_msg, json_temp_clicks])

        # -- Dock -- #
        btn_reg_dock.click(gh.on_register_dock, [robot_dropdown, txt_dock_name], action_result)
        btn_refresh_dock.click(gh.refresh_dock_choices, robot_dropdown, dd_dock_list)
        btn_del_dock.click(gh.on_delete_dock, [robot_dropdown, dd_dock_list], action_result)
        btn_go_home.click(gh.on_go_home, robot_dropdown, action_result)
        
        # -- POI (Consolidated) -- #
        btn_refresh_poi.click(gh.refresh_poi_choices_api, robot_dropdown, dd_poi_api_list)
        
        # Load POI into edit fields on select
        dd_poi_api_list.change(gh.on_poi_select_for_edit, [robot_dropdown, dd_poi_api_list], [txt_poi_edit_id, txt_poi_edit_name, dd_poi_edit_type, num_poi_x, num_poi_y, num_poi_yaw, action_result])
        
        # POI Actions
        btn_add_poi_robot.click(gh.on_add_poi_at_robot, [robot_dropdown, txt_poi_edit_name, dd_poi_edit_type], [action_result, dd_poi_api_list])
        btn_add_poi_click.click(gh.on_add_poi_at_click, [robot_dropdown, txt_poi_edit_name, dd_poi_edit_type, target_coords_json], [action_result, dd_poi_api_list])
        btn_save_poi.click(gh.on_update_poi_confirm, [robot_dropdown, txt_poi_edit_id, txt_poi_edit_name, dd_poi_edit_type, num_poi_x, num_poi_y, num_poi_yaw], [action_result, dd_poi_api_list])
        btn_del_poi_api.click(gh.on_delete_poi, [robot_dropdown, dd_poi_api_list], action_result)
        btn_adjust_poi.click(gh.on_adjust_pois, robot_dropdown, action_result)

        poi_dummy = gr.State([]) 
        timer = gr.Timer(value=0.1)
        timer.tick(gh.update_ui_wrapper, inputs=[robot_dropdown, chk_map, chk_lidar_rays, chk_lidar_points, chk_robot, chk_axis, poi_dummy, chk_traj, chk_path, st_target, st_pose, st_status, st_health], outputs=[json_pose, json_lidar, json_map, json_areas, json_lines, txt_dashboard, st_pose, st_status, st_health, btn_clear_error])
        
        demo.load(None, None, None, js=js_loader)
        return demo