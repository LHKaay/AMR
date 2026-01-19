import os
import paramiko
from scp import SCPClient
import yaml

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)["amrs"]

# def create_ssh_client(host, user, password):
#     ssh = paramiko.SSHClient()
#     ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#     ssh.connect(hostname=host, username=user, password=password)
#     return ssh

def create_ssh_client(host, user, port=22, password=None, key_path="~/.ssh/id_rsa"):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if port==22:
        ssh.connect(
            hostname=host,
            port=port,
            username=user,
            password=password,
            look_for_keys=False,
            allow_agent=False,
        )
    else:
        ssh.connect(
            hostname=host,
            port=port,
            username=user,
            key_filename=os.path.expanduser(key_path),
            look_for_keys=False,
            allow_agent=False,
        )

    return ssh

def run_command(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode(), stderr.read().decode()
        
def upload_path(ssh, local_path, remote_path):
    if not os.path.isdir(local_path):
        raise ValueError(f"Not a directory: {local_path}")

    ssh.exec_command(f"mkdir -p {remote_path}")

    with SCPClient(ssh.get_transport()) as scp:
        for item in os.listdir(local_path):
            src = os.path.join(local_path, item)
            scp.put(src, remote_path, recursive=True)