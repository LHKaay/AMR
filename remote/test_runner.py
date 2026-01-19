from ssh_utils import run_command
    
def run_test(ssh, test_path):
    cmd = f"python3 {test_path}"
    out, err = run_command(ssh, cmd)
    return out, err


# def run_test(ssh, branch, base_dir):
#     test_path = f"{base_dir}/{branch}/test.py"
#     cmd = f"python3 {test_path}"
#     out, err = run_command(ssh, cmd)
#     return out, err