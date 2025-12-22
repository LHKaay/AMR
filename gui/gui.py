import gradio as gr
from .gui_schema import GUI_SCHEMA
from .gui_action import GUI_ACTIONS
from .gui_state import GUI_State


COMPONENTS = {}

def update_state(states, changes):
    """
    Updates the GUI state dictionary by applying the provided key-value changes.
    args:
     - states: dict holding the current shared GUI state.
     - changes: dict of key-value pairs to merge into the state.
    return:
     - dict: the updated state dictionary.
    """
    for k, v in changes.items():
        states[k] = v
    return states

def state_change(states):
    """
    Computes and returns Gradio component updates based on the current navigation section and telemetry values.
    args:
     - states: dict holding the current shared GUI state.
    return:
     - tuple: a tuple of gr.update objects and values to drive component visibility and labels.
    """
    return (
        gr.update(visible=(states["navigation_section"] == "AMR")),
        gr.update(visible=(states["navigation_section"] == "Map")),
        gr.update(visible=(states["navigation_section"] == "Camera")),
        gr.update(visible=(states["navigation_section"] == "Arm")),
        gr.update(value=states.get("robot_speed", 0)),
        gr.update(value=f"Battery status: {states.get('battery_percentage', 'N/A')}%  ; Current pose: ({states.get('robot_pose', '(x, y, yaw)')})")
        
    )

def dispatch(fn_name: str, state: dict, *args):
    """
    Looks up a GUI action by name and executes it with the given state and arguments, returning the updated state.
    args:
     - fn_name: str name of the action function to invoke.
     - state: dict representing the current shared GUI state.
     - *args: additional positional arguments forwarded to the action.
    return:
     - dict: the potentially updated GUI state returned by the action.
    """
    # Ignore if no function defined in schema
    if not fn_name or fn_name == "None":
        return state
    
    fn = GUI_ACTIONS.get(fn_name)
    
    if not fn:
        print(f"[WARNING] Unknown action → {fn_name}")
        return state
    
    # Call the action function with state and extra args
    new_state = fn(state, *args)
    
    # Always return updated state back to Gradio
    return new_state


with gr.Blocks(title="MSIS AMR", fill_height=True) as demo:
    STATES = gr.State(GUI_State().to_dict())

    with gr.Row(elem_classes="nav-bar"):
        with gr.Row(elem_classes="nav-buttons"):
            for nav_item in GUI_SCHEMA["navigation"]:
                # Instantiate component and store in registry
                comp_instance = nav_item["component"](**nav_item["props"])
                COMPONENTS[nav_item["name"]] = comp_instance
                comp_instance.click(
                    fn=eval(nav_item["click"]["fn"]),
                    inputs=[STATES, gr.State(nav_item["click"]["inputs"])],
                    outputs=[STATES]
                )

        comp_instance = GUI_SCHEMA["logo"]["component"](**GUI_SCHEMA["logo"]["props"])
        COMPONENTS[GUI_SCHEMA["logo"]["name"]] = comp_instance

    with gr.Row(elem_classes="main-container"):
        with gr.Sidebar(width=400, elem_classes="menu-sidebar"):
            with gr.Group(visible=True) as general_controls:
                with gr.Row():
                    for item in GUI_SCHEMA["general_controls"]:
                        # Instantiate component and store in registry
                        comp_instance = item["component"](**item["props"])
                        COMPONENTS[item["name"]] = comp_instance
                        if item["component"] == gr.Button:
                            comp_instance.click(
                                fn=dispatch,
                                inputs=[gr.State(item["fn"]), STATES],
                                outputs=[STATES]
                            )
            
            with gr.Group(visible=True) as box_amr:
                gr.Markdown("### AMR Controls")

                for item in GUI_SCHEMA["amr_controls"]:
                    with gr.Accordion(f"{list(item.keys())[0]}", open=False):
                        for sub_item in item[f"{list(item.keys())[0]}"]:
                            comp_instance = sub_item["component"](**sub_item["props"])
                            COMPONENTS[sub_item["name"]] = comp_instance
                            
                            if sub_item["component"] == gr.Button:
                                comp_instance.click(
                                    fn=dispatch,
                                    inputs=[gr.State(sub_item["fn"]), STATES],
                                    outputs=[STATES]
                                )
                            elif sub_item["component"] != gr.Button:
                                comp_instance.change(
                                    fn=dispatch,
                                    inputs=[gr.State(sub_item["fn"]), STATES, gr.State(sub_item['name']) , comp_instance],
                                    outputs=[STATES]
                                )
                
            with gr.Group(visible=False) as box_map:
                gr.Markdown("### Map Controls")
         
            with gr.Group(visible=False) as box_camera:
                gr.Markdown("### Camera Controls")
                
            with gr.Group(visible=False) as box_arm:
                gr.Markdown("### Arm Controls")

        with gr.Row(elem_classes="amr_info_row"):
            btn_refresh_info = gr.Button("⟳", elem_classes="reload-btn", min_width=30)
            btn_refresh_info.click(
                fn=lambda state: dispatch("update_amr_info", state),
                inputs=[STATES],
                outputs=[STATES]
            )
            amr_info = gr.Label(
                "Battery status: - %  ; Current pose: (x, y, yaw)",
                show_label=False,
                elem_classes="amr_info"
            )

        gr.Timer(0.05).tick(
            fn=lambda state: dispatch("update_amr_info", state),
            inputs=[STATES],
            outputs=[STATES],
            show_progress="hidden"
        )

        with gr.Column(scale=9):
            gr.Markdown("### Arm Controls")

    gr.Model3D("gui/assest/MSIS_AMR.glb", show_label=False, elem_id="msis_amr_3dviewer")

    STATES.change(
        state_change,
        inputs=[STATES],
        outputs=[box_amr, box_map, box_camera, box_arm,
                COMPONENTS['robot_speed'],
                amr_info],
        show_progress="hidden"
    )

    demo.load(None, None, None, js=open(f"gui/{GUI_SCHEMA['js_file']}", encoding='utf-8').read())
