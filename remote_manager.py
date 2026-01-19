import os

from utils import create_ssh_client, upload_path, run_command

def get_selected_amrs(selected_targets, amrs):
    return [j for j in amrs if j["name"] in selected_targets]

def upload_from_pc(
    selected_targets,
    amrs,
    local_path,
    branch,
    prev_logs=""
):
    logs = prev_logs or ""

    if not os.path.exists(local_path):
        logs += f"[ERROR] Local path not found: {local_path}\n"
        return logs, logs

    for target in get_selected_amrs(selected_targets, amrs):
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

def run_test(ssh, test_path):
    cmd = f"python3 {test_path}"
    out, err = run_command(ssh, cmd)
    return out, err

def run_test_branch(
    selected_targets,
    amrs,
    branch,
    prev_logs=""
):
    logs = prev_logs or ""
    
    for target in get_selected_amrs(selected_targets, amrs):
        remote_path = f"{target['base_dir']}/{branch}/test.py"
        ssh = create_ssh_client(target["host"], target["user"], target["port"], target["password"], target["key"])
        out, err = run_test(ssh, remote_path)
        logs += f"[{target['name']}]\n{out}\n{err}\n"
        ssh.close()
    return logs, logs