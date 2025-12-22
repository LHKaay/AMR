
import sys
import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
sys.path.append(BASE_DIR)

import time
import threading
import json
import copy
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from fairino import Robot  

"""
MSIS AMR TEAM Project

Features:
- Control buttons: STOP, PAUSE, RESUME
- 6 joint movement buttons (MoveJ for each joint)
- Save/load pick and place poses (Cartesian coordinates)
- Configurable number of boxes and box height
- Pick-and-place stacking automation
"""

# ===== Global robot instance and flags =====
robot = None
stop_flag = False
pause_flag = False
robot_lock = threading.Lock()  #to prevent simultanous concurrent robot commands

# ===== Default configuration =====
DEFAULT_ROBOT_IP = "192.168.58.3"
GRIPPER_INDEX = 1
GRIP_SPEED = 90
GRIP_FORCE = 50
GRIP_MAX_TIME = 30000
GRIP_BLOCK = 0

TOOL = 0
USER = 0
VEL = 20
BLENDT = 100

# Joint increments (degrees)
JOINT_INCREMENT = 5 #change based on how much u want to move joint on a single click

# Default poses (Cartesian: [x, y, z, rx, ry, rz])
DEFAULT_PICK_POSE = [198.45, 361.97, 373.7, 178.27, -1.419, 141.776]
DEFAULT_PLACE_POSE = [-245.46, -420.488, 148.68, -179.71, 1.228, -35.907]
DEFAULT_SAFE_PICK = [138.812, 287.380, 521.817, 173.107, -1.087, 140.347]
DEFAULT_SAFE_PLACE = [-175.52, -320.94, 491.52, 179.57, 0.597, -39.545]
home_pose= [-36.941, -164.450, 522.661, 158.734, 6.237, -37.809]#[182.082, 340.817, 475.358, 175.088, 2.385, 142.770]#check to avoid crash

DEFAULT_NUM_BOXES = 4
DEFAULT_BOX_HEIGHT = 48.0
DEFAULT_APPROACH_OFFSET = 40.0

POSES_FILE = "saved_poses.json"


# ===== Robot connection =====
def connect_robot(ip):
    global robot
    try:
        robot = Robot.RPC(ip)
        robot.SetSpeed(VEL)
        robot.ActGripper(GRIPPER_INDEX, 1)
        return True, "Robot connected successfully"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def disconnect_robot():
    global robot
    if robot:
        try:
            robot.CloseRPC()
            robot = None
            return True, "Robot disconnected"
        except Exception as e:
            return False, f"Disconnect failed: {str(e)}"
    return False, "Robot not connected"


# ===== Safety controls =====
def stop_robot():
    """Stop robot immediately - need to be fixed."""
    global stop_flag, pause_flag
    stop_flag = True
    pause_flag = False
    if robot:
        try:
            robot.StopMotion()
        except Exception:
            pass


def pause_robot():
    """Pause robot immediately - ."""
    global pause_flag
    pause_flag = True
    if robot:
        try:
            robot.PauseMotion()
        except Exception:
            pass


def resume_robot():
    """Resume paused robot immediately - does NOT hold lock."""
    global pause_flag
    pause_flag = False
    if robot:
        try:
            robot.ResumeMotion()
        except Exception:
            pass

def go_home(pose):#if called should go to the predifined home pose
    if stop_flag:
        return False
    if not move_cart(pose):
        return False 


def reset_flags():
    global stop_flag, pause_flag
    with robot_lock:
        stop_flag = False
        pause_flag = False


def wait_while_paused():
    """Wait while robot is paused or stopped. Does NOT acquire lock."""
    while True:
        if stop_flag:
            return False
        if not pause_flag:
            return True
        time.sleep(0.05)


# ===== Gripper controls =====
def open_gripper():
    if not robot:
        return False
    if stop_flag or pause_flag:
        return False
    try:
        with robot_lock:
            robot.MoveGripper(GRIPPER_INDEX, 100, GRIP_SPEED, GRIP_FORCE, GRIP_MAX_TIME, GRIP_BLOCK, 0, 0, 0, 0)
        return True
    except Exception as e:
        print(f"Open gripper error: {e}")
        return False


def close_gripper(angle=60):#cuurently 60 for white box
    if not robot:
        return False
    if stop_flag or pause_flag:
        return False
    try:
        with robot_lock:
            robot.MoveGripper(GRIPPER_INDEX, angle, GRIP_SPEED, GRIP_FORCE, GRIP_MAX_TIME, GRIP_BLOCK, 0, 0, 0, 0)
        return True
    except Exception as e:
        print(f"Close gripper error: {e}")
        return False


# ===== Joint movement =====
def move_joint_worker(joint_index, direction, gui_callback=None):
    """Worker function: move a specific joint (runs in background thread).
    joint_index: 0-5 (joint 1-6)
    direction: 1 for positive, -1 for negative
    gui_callback: function to call with (title, message, is_error)
    """
    if not robot:
        if gui_callback:
            gui_callback("Error", "Robot not connected", True)
        return

    try:
        with robot_lock:
            # Get current joint state
            ret, jpos = robot.GetActualJointPosDegree()
            if ret == 0 and jpos:
                # Modify target joint
                target_jpos = list(jpos)
                target_jpos[joint_index] += direction * JOINT_INCREMENT

                # MoveJ with joint coordinates
                robot.MoveJ(joint_pos=target_jpos, tool=TOOL, user=USER, vel=VEL, blendT=BLENDT)
        
        # Wait for motion to complete (outside lock)
        if not wait_while_paused():
            if gui_callback:
                gui_callback("Info", "Joint movement stopped", False)
            return

        if gui_callback:
            gui_callback("Success", f"Joint {joint_index + 1} moved {direction * JOINT_INCREMENT}°", False)
    except Exception as e:
        if gui_callback:
            gui_callback("Error", f"Joint move failed: {str(e)}", True)


def move_joint(joint_index, direction, gui_callback=None):
    """Trigger joint movement in background thread to prevent GUI freeze."""
    if not robot:
        messagebox.showerror("Error", "Robot not connected")
        return
    
    # Run in background thread
    thread = threading.Thread(target=move_joint_worker, args=(joint_index, direction, gui_callback), daemon=True)
    thread.start()


# ===== Cartesian movement =====
def move_cart(pose, velocity=None):
    """Move to Cartesian pose and wait. velocity parameter overrides default VEL."""
    if not robot:
        return False
    
    if stop_flag:
        return False

    try:
        vel = velocity if velocity is not None else VEL
        with robot_lock:
            robot.MoveCart(desc_pos=pose, tool=TOOL, user=USER, vel=vel, blendT=BLENDT)

        # Wait while paused or for stop (outside lock)
        if not wait_while_paused():
            return False

        return True
    except Exception as e:
        print(f"Cartesian move error: {e}")
        return False


def get_current_pose():
    """Get current Cartesian pose."""
    if not robot:
        return None
    try:
        with robot_lock:
            ret, pose = robot.GetActualTCPPose()
            if ret == 0 and pose:
                return pose
    except Exception as e:
        print(f"Get pose error: {e}")
    return None


# ===== Pose save/load =====
def load_poses():
    """Load saved poses from file."""
    try:
        with open(POSES_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = None
    except Exception as e:
        print(f"Load error: {e}")
        data = None

    # Default structure with 5 tables
    def default_tables():
        tables = {}
        for i in range(1, 6):
            tables[str(i)] = {
                "pick_pose": DEFAULT_PICK_POSE,
                "place_pose": DEFAULT_PLACE_POSE,
                "safe_pick": DEFAULT_SAFE_PICK,
                "safe_place": DEFAULT_SAFE_PLACE
            }
        return tables

    if not data:
        return {
            "tables": default_tables(),
            "num_boxes": DEFAULT_NUM_BOXES,
            "box_height": DEFAULT_BOX_HEIGHT,
            "approach_offset": DEFAULT_APPROACH_OFFSET
        }

    # Backwards compatibility: old flat format -> migrate into table '1'
    if any(k in data for k in ("pick_pose", "place_pose", "safe_pick", "safe_place")):
        tables = default_tables()
        tables["1"]["pick_pose"] = data.get("pick_pose", DEFAULT_PICK_POSE)
        tables["1"]["place_pose"] = data.get("place_pose", DEFAULT_PLACE_POSE)
        tables["1"]["safe_pick"] = data.get("safe_pick", DEFAULT_SAFE_PICK)
        tables["1"]["safe_place"] = data.get("safe_place", DEFAULT_SAFE_PLACE)
        return {
            "tables": tables,
            "num_boxes": data.get("num_boxes", DEFAULT_NUM_BOXES),
            "box_height": data.get("box_height", DEFAULT_BOX_HEIGHT),
            "approach_offset": data.get("approach_offset", DEFAULT_APPROACH_OFFSET)
        }

    # If data already in new format, ensure tables exist
    if "tables" not in data:
        data["tables"] = default_tables()
    else:
        # fill missing tables
        for i in range(1, 6):
            key = str(i)
            if key not in data["tables"]:
                data["tables"][key] = {
                    "pick_pose": DEFAULT_PICK_POSE,
                    "place_pose": DEFAULT_PLACE_POSE,
                    "safe_pick": DEFAULT_SAFE_PICK,
                    "safe_place": DEFAULT_SAFE_PLACE
                }
            else:
                # ensure all four poses exist for the table
                tbl = data["tables"][key]
                tbl.setdefault("pick_pose", DEFAULT_PICK_POSE)
                tbl.setdefault("place_pose", DEFAULT_PLACE_POSE)
                tbl.setdefault("safe_pick", DEFAULT_SAFE_PICK)
                tbl.setdefault("safe_place", DEFAULT_SAFE_PLACE)

    # Ensure top-level params
    data.setdefault("num_boxes", DEFAULT_NUM_BOXES)
    data.setdefault("box_height", DEFAULT_BOX_HEIGHT)
    data.setdefault("approach_offset", DEFAULT_APPROACH_OFFSET)
    data.setdefault("vel", VEL)
    data.setdefault("vel_slow", VEL)

    return data


def save_poses(data):
    """Save poses to file."""
    try:
        with open(POSES_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Save error: {e}")
        return False


# ===== Pick and place logic =====
def set_pose_z(pose, z):
    p = copy.deepcopy(pose)
    p[2] = z
    return p


def pick_and_place_one(pick_base, place_base, safe_pick, safe_place, pick_z, place_z, approach_offset, vel_normal=None, vel_slow=None, status_callback=None):
    """Performs pick and place for a single box using safe waypoint poses.
    vel_normal: normal movement speed (default VEL)
    vel_slow: slow movement speed for fine approach (default VEL)
    """
    if stop_flag:
        return False

    vel_n = vel_normal if vel_normal is not None else VEL
    vel_s = vel_slow if vel_slow is not None else VEL

    target_pick = set_pose_z(pick_base, pick_z)
    target_place = set_pose_z(place_base, place_z)

    # Move to safe pick position first
    if status_callback:
        status_callback("Moving to safe pick position...")
    if not move_cart(safe_pick, vel_n):
        return False

    # Approach and pick (use slow speed for final approach)
    if status_callback:
        status_callback("Approaching pick position...")
    if not move_cart(target_pick, vel_s):
        return False

    if status_callback:
        status_callback("Closing gripper...")
    close_gripper()
    time.sleep(0.15)

    # Return to safe pick position
    if status_callback:
        status_callback("Returning to safe position...")
    if not move_cart(safe_pick, vel_n):
        return False

    # Move to safe place position
    if status_callback:
        status_callback("Moving to safe place position...")
    if not move_cart(safe_place, vel_n):
        return False

    # Approach and place (use slow speed for final approach)
    if status_callback:
        status_callback("Approaching place position...")
    if not move_cart(target_place, vel_n):
        return False

    if status_callback:
        status_callback("Opening gripper...")
    open_gripper()
    time.sleep(0.15)

    # Return to safe place position
    if status_callback:
        status_callback("Returning to safe position...")
    if not move_cart(safe_place, vel_n):
        return False

    return True


def run_stacking_sequence(pick_pose, place_pose, safe_pick, safe_place, num_boxes, box_height, approach_offset, status_callback=None, vel_normal=None, vel_slow=None):
    """Run the stacking sequence in background -."""
    global stop_flag, pause_flag

    reset_flags()

    for i in range(num_boxes):
        # Check for stop before each box
        if stop_flag:
            if status_callback:
                status_callback("Operation stopped by user")
            break

        # Wait if paused
        while pause_flag and not stop_flag:
            if status_callback:
                status_callback("Paused - waiting for resume...")
            time.sleep(0.2)

        pick_z = pick_pose[2] - i * box_height
        place_z = place_pose[2] + i * box_height

        if status_callback:
            status_callback(f"\n--- Box {i+1}/{num_boxes} ---")
            status_callback(f"Pick Z: {pick_z:.3f}  Place Z: {place_z:.3f}")

        ok = pick_and_place_one(pick_pose, place_pose, safe_pick, safe_place, pick_z, place_z, approach_offset, vel_normal, vel_slow, status_callback)
        if not ok:
            if status_callback:
                status_callback("Pick-and-place aborted")
            break

        time.sleep(0.2)

    if status_callback:
        status_callback("Stacking sequence completed")
