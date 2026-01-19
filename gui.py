import gradio as gr

from remote_manager import upload_from_pc, run_test_branch

def run_gui(amrs):
    
    amr_names = [a["name"] for a in amrs]
    
    with gr.Blocks(title="AMR Remote Manager") as demo:
        gr.Markdown("## AMR Remote Manager")

        amr_select = gr.CheckboxGroup(
            choices=amr_names,
            label="Select AMR Name"
        )

        with gr.Group():
            gr.Markdown("### 📤 Upload Folder")

            with gr.Row():
                with gr.Column(scale=3):
                    local_path_input = gr.Textbox(
                        label="Server Directory",
                        placeholder="/home/msis/example"
                    )

                    upload_branch = gr.Radio(
                        ["Arm", "AMR", "Camera", "Map"],
                        label="Upload Branch",
                        value="Arm"
                    )

                with gr.Column(scale=1, min_width=120):
                    upload_btn = gr.Button("Upload", variant="primary")
        
        with gr.Group():
            gr.Markdown("### ▶️ Test Code")
            
            with gr.Row():
                with gr.Column(scale=3):
                    test_branch = gr.Radio(
                        ["Arm", "AMR", "Camera", "Map"],
                        label="Test Branch",
                        value="Arm"
                    )
                with gr.Column(scale=1, min_width=120):
                    test_btn = gr.Button("Run Test", variant="primary")

        log_box = gr.Textbox(lines=20, label="Logs")
        log_state = gr.State("")
        upload_path_state = gr.State("")
        
        upload_btn.click(
            upload_from_pc, 
            [amr_select, gr.State(amrs), local_path_input, upload_branch, log_state], 
            [log_box, log_state]
        )

        test_btn.click(
            run_test_branch, 
            [amr_select, gr.State(amrs), test_branch, log_state], 
            [log_box, log_state]
        )


    demo.launch(server_name="0.0.0.0", server_port=7860)