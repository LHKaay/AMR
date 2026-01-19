import os
import gradio as gr
import yaml
from ssh_utils import create_ssh_client, upload_path, run_command
from test_runner import run_test

with open("config.yaml") as f:
    AMRS = yaml.safe_load(f)["amrs"]

AMR_NAMES = [j["name"] for j in AMRS]

def get_selected_amrs(selected):
    return [j for j in AMRS if j["name"] in selected]

def enforce_single_selection(selected):
    if not selected:
        return []

    return [selected[-1]]

def list_remote_dirs(ssh, path):
    cmd = f"ls -d {path}/*/ 2>/dev/null"
    out, _ = run_command(ssh, cmd)

    dirs = [d.rstrip("/").split("/")[-1] for d in out.splitlines()]
    return dirs

def list_remote_items(ssh, path):
    cmd = f"ls -p {path} 2>/dev/null"
    out, _ = run_command(ssh, cmd)

    dirs = []
    files = []

    for line in out.splitlines():
        if line.endswith("/"):
            dirs.append(line.rstrip("/"))
        else:
            files.append(line)

    return sorted(dirs), sorted(files)

def init_upload_dirs(selected_targets):
    if not selected_targets:
        return (gr.update(choices=[], value=None), "", "")

    target = get_selected_amrs(selected_targets)[0]
    base = target["base_dir"]

    ssh = create_ssh_client(target["host"], target["user"], target["port"], target["password"], target["key"])

    dirs = list_remote_dirs(ssh, base)
    ssh.close()

    choices = [".."] + dirs if base != "/" else dirs

    return (gr.update(choices=choices, value=None), base, base)

def navigate_upload_dir(
    selected_dir,
    current_path,
    selected_targets
):
    if not selected_dir or not selected_targets:
        return gr.update(), current_path, current_path

    target = get_selected_amrs(selected_targets)[0]

    if selected_dir == "..":
        new_path = os.path.dirname(current_path.rstrip("/"))
        if new_path == "":
            new_path = "/"
    else:
        new_path = f"{current_path.rstrip('/')}/{selected_dir}"

    ssh = create_ssh_client(target["host"], target["user"], target["port"], target["password"], target["key"])

    dirs = list_remote_dirs(ssh, new_path)
    ssh.close()

    choices = [".."] + dirs if new_path != "/" else dirs

    return (gr.update(choices=choices, value=None), new_path, new_path)

def upload_from_pc(
    selected_targets,
    local_path,
    branch,
    prev_logs=""
):
    logs = prev_logs or ""

    if not os.path.exists(local_path):
        logs += f"[ERROR] Local path not found: {local_path}\n"
        return logs, logs

    for target in get_selected_amrs(selected_targets):
        ssh = create_ssh_client(target["host"], target["user"], target["port"], target["password"], target["key"])

        remote_path = f"{target['base_dir']}/{branch}/."

        upload_path(ssh, local_path, remote_path)

        logs += (
            f"[{target['name']}] Uploaded\n"
            f"  PC: {local_path}\n"
            f"  → Jetson: {remote_path}\n"
        )

        ssh.close()

    return logs, logs



def build_file_browser_choices(dirs, files):
    choices = []

    choices.append("..")

    for d in dirs:
        choices.append(f"📁 {d}")

    for f in files:
        choices.append(f"📄 {f}")

    return choices

def init_test_dirs(selected_targets):
    if not selected_targets:
        return gr.update(choices=[], value=None), "", ""

    target = get_selected_amrs(selected_targets)[0]
    base = target["base_dir"]

    ssh = create_ssh_client(target["host"], target["user"], target["port"], target["password"], target["key"])

    dirs, files = list_remote_items(ssh, base)
    ssh.close()

    choices = build_file_browser_choices(dirs, files)

    return gr.update(choices=choices, value=None), base, ""

def navigate_test_dir(
    selected_item,
    current_path,
    selected_targets
):
    if not selected_item or not selected_targets:
        return gr.update(), current_path, current_path

    target = get_selected_amrs(selected_targets)[0]
    ssh = create_ssh_client(target["host"], target["user"], target["port"], target["password"], target["key"])
    
    # 상위 이동
    if selected_item == "..":
        new_path = os.path.dirname(current_path.rstrip("/")) or "/"

        dirs, files = list_remote_items(ssh, new_path)
        ssh.close()

        choices = build_file_browser_choices(dirs, files)
        return gr.update(choices=choices, value=None), new_path, new_path

    # 디렉토리 클릭
    if selected_item.startswith("📁 "):
        dirname = selected_item.replace("📁 ", "", 1)
        new_path = f"{current_path.rstrip('/')}/{dirname}"

        dirs, files = list_remote_items(ssh, new_path)
        ssh.close()

        choices = build_file_browser_choices(dirs, files)
        return gr.update(choices=choices, value=None), new_path, new_path

    # 파일 클릭
    if selected_item.startswith("📄 "):
        filename = selected_item.replace("📄 ", "", 1)
        full_path = f"{current_path.rstrip('/')}/{filename}"
        ssh.close()
        
        return gr.update(value=selected_item), current_path, full_path

    ssh.close()
    return gr.update(), current_path, current_path

def run_test_selected_file(
    selected_targets,
    remote_path,
    prev_logs=""
):
    logs = prev_logs or ""

    remote_path
    for target in get_selected_amrs(selected_targets):
        ssh = create_ssh_client(target["host"], target["user"], target["port"], target["password"], target["key"])
        out, err = run_test(ssh, remote_path)
        logs += f"[{target['name']}]\n{out}\n{err}\n"
        ssh.close()
    return logs, logs

def run_test_branch(
    selected_targets,
    branch,
    prev_logs=""
):
    logs = prev_logs or ""
    
    for target in get_selected_amrs(selected_targets):
        remote_path = f"{target['base_dir']}/{branch}/test.py"
        ssh = create_ssh_client(target["host"], target["user"], target["port"], target["password"], target["key"])
        out, err = run_test(ssh, remote_path)
        logs += f"[{target['name']}]\n{out}\n{err}\n"
        ssh.close()
    return logs, logs

with gr.Blocks(title="AMR Remote Manager") as demo:
    gr.Markdown("## AMR Remote Manager")

    amr_select = gr.CheckboxGroup(
        choices=AMR_NAMES,
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
    
    # test_path_state = gr.State("")
    # test_file_state = gr.State("")
    
    upload_btn.click(
        upload_from_pc, 
        [amr_select, local_path_input, upload_branch, log_state], 
        [log_box, log_state]
    )


    test_btn.click(
        run_test_branch, 
        [amr_select, test_branch, log_state], 
        [log_box, log_state]
    )


demo.launch(server_name="0.0.0.0", server_port=7860)