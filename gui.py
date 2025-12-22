
import time
import threading
import json
import copy
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from fairino import Robot

from MSIS_robot_control import *
class RobotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Fairino Robot Control")
        self.root.geometry("900x800")

        self.poses_data = load_poses()

        
        self.left_frame = ttk.Frame(root)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ===== Connection Frame =====
        self.conn_frame = ttk.LabelFrame(self.left_frame, text="Robot Connection", padding=10)
        self.conn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(self.conn_frame, text="Robot IP:").grid(row=0, column=0, sticky=tk.W)
        self.ip_var = tk.StringVar(value=DEFAULT_ROBOT_IP)
        ttk.Entry(self.conn_frame, textvariable=self.ip_var, width=20).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(self.conn_frame, text="Connect", command=self.connect).grid(row=0, column=2, padx=5)
        ttk.Button(self.conn_frame, text="Disconnect", command=self.disconnect).grid(row=0, column=3, padx=5)

        self.status_label = ttk.Label(self.conn_frame, text="Status: Disconnected", foreground="red")
        self.status_label.grid(row=0, column=4, padx=10)

        # ===== Control Frame =====
        self.ctrl_frame = ttk.LabelFrame(self.left_frame, text="Robot Controls", padding=10)
        self.ctrl_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(self.ctrl_frame, text="STOP", command=stop_robot, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.ctrl_frame, text="PAUSE", command=pause_robot, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.ctrl_frame, text="RESUME", command=resume_robot, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.ctrl_frame, text="GO HOME", command=lambda: self.go_home_action(), width=15).pack(side=tk.LEFT, padx=5)

        # ===== Joint Movement Frame =====
        self.joint_frame = ttk.LabelFrame(self.left_frame, text="Joint Movement (±5°)", padding=10)
        self.joint_frame.pack(fill=tk.X, padx=10, pady=5)

        for i in range(6):
            sub_frame = ttk.Frame(self.joint_frame)
            sub_frame.pack(fill=tk.X, padx=5, pady=3)

            ttk.Label(sub_frame, text=f"Joint {i+1}:", width=10).pack(side=tk.LEFT)
            ttk.Button(sub_frame, text="←", width=3, command=lambda j=i: move_joint(j, -1, self.joint_callback)).pack(side=tk.LEFT, padx=2)
            ttk.Button(sub_frame, text="→", width=3, command=lambda j=i: move_joint(j, 1, self.joint_callback)).pack(side=tk.LEFT, padx=2)

        # ===== Gripper Frame =====
        self.gripper_frame = ttk.LabelFrame(self.left_frame, text="Gripper Control", padding=10)
        self.gripper_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(self.gripper_frame, text="Open Gripper", command=lambda: open_gripper(), width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.gripper_frame, text="Close Gripper", command=lambda: close_gripper(), width=20).pack(side=tk.LEFT, padx=5)

        # ===== Current Pose Frame =====
        self.pose_frame = ttk.LabelFrame(self.left_frame, text="Current Pose (Cartesian)", padding=10)
        self.pose_frame.pack(fill=tk.X, padx=10, pady=5)

        self.pose_label = ttk.Label(self.pose_frame, text="Not available", font=("Courier", 9))
        self.pose_label.pack()

        ttk.Button(self.pose_frame, text="Refresh Pose", command=self.refresh_pose).pack(pady=5)

        # ===== Pose Save/Load Frame =====
        self.save_frame = ttk.LabelFrame(self.left_frame, text="Pose Management", padding=10)
        self.save_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(self.save_frame, text="Save Pick Pose", command=self.save_pick_pose, width=18).pack(side=tk.LEFT, padx=3)
        ttk.Button(self.save_frame, text="Save Safe Pick", command=self.save_safe_pick_pose, width=18).pack(side=tk.LEFT, padx=3)
        ttk.Button(self.save_frame, text="Save Place Pose", command=self.save_place_pose, width=18).pack(side=tk.LEFT, padx=3)
        ttk.Button(self.save_frame, text="Save Safe Place", command=self.save_safe_place_pose, width=18).pack(side=tk.LEFT, padx=3)
        ttk.Button(self.save_frame, text="View Saved Poses", command=self.view_poses, width=18).pack(side=tk.LEFT, padx=3)

        # ===== Stacking Parameters Frame =====
        self.param_frame = ttk.LabelFrame(self.left_frame, text="Stacking Parameters", padding=10)
        self.param_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(self.param_frame, text="Number of Boxes:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.num_boxes_var = tk.IntVar(value=self.poses_data.get("num_boxes", DEFAULT_NUM_BOXES))
        ttk.Entry(self.param_frame, textvariable=self.num_boxes_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(self.param_frame, text="Box Height (mm):").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.box_height_var = tk.DoubleVar(value=self.poses_data.get("box_height", DEFAULT_BOX_HEIGHT))
        ttk.Entry(self.param_frame, textvariable=self.box_height_var, width=10).grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(self.param_frame, text="Approach Offset (mm):").grid(row=0, column=4, sticky=tk.W, padx=5)
        self.offset_var = tk.DoubleVar(value=self.poses_data.get("approach_offset", DEFAULT_APPROACH_OFFSET))
        ttk.Entry(self.param_frame, textvariable=self.offset_var, width=10).grid(row=0, column=5, sticky=tk.W, padx=5)

        # Table selector (1-5)
        ttk.Label(self.param_frame, text="Table:").grid(row=0, column=6, sticky=tk.W, padx=5)
        self.table_var = tk.StringVar(value="1")
        self.table_combo = ttk.Combobox(self.param_frame, textvariable=self.table_var, values=["1","2","3","4","5"], width=5, state="readonly")
        self.table_combo.grid(row=0, column=7, sticky=tk.W, padx=5)

        # Speed controls - add to second row
        ttk.Label(self.param_frame, text="Normal Speed (%):").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.vel_var = tk.DoubleVar(value=self.poses_data.get("vel", VEL))
        ttk.Entry(self.param_frame, textvariable=self.vel_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(self.param_frame, text="Slow Speed (%):").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.vel_slow_var = tk.DoubleVar(value=self.poses_data.get("vel_slow", VEL))
        ttk.Entry(self.param_frame, textvariable=self.vel_slow_var, width=10).grid(row=1, column=3, sticky=tk.W, padx=5)

        ttk.Button(self.param_frame, text="Save Parameters", command=self.save_parameters).grid(row=1, column=4, columnspan=2, sticky=tk.W, padx=5)

        # ===== Stacking Control Frame =====
        self.run_frame = ttk.LabelFrame(self.left_frame, text="Stacking Control", padding=10)
        self.run_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(self.run_frame, text="Start Stacking", command=self.start_stacking, width=20).pack(side=tk.LEFT, padx=5)

        # ===== Status Output Frame =====
        
        self.output_frame = ttk.LabelFrame(root, text="Status Output", padding=10)
        self.output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.output_text = tk.Text(self.output_frame, height=20, width=60, font=("Courier", 9))
        self.output_text.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self.output_frame, orient=tk.VERTICAL, command=self.output_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=scrollbar.set)

    def connect(self):
        ip = self.ip_var.get()
        ok, msg = connect_robot(ip)
        if ok:
            self.status_label.config(text="Status: Connected", foreground="green")
            self.log(f"✓ {msg}")
        else:
            self.status_label.config(text="Status: Failed", foreground="red")
            self.log(f"✗ {msg}")
            messagebox.showerror("Connection Error", msg)

    def joint_callback(self, title, message, is_error):
        """Callback for joint movement status (called from worker thread)."""
        if is_error:
            self.log(f"✗ {message}")
        else:
            self.log(f"✓ {message}")

    def disconnect(self):
        ok, msg = disconnect_robot()
        if ok:
            self.status_label.config(text="Status: Disconnected", foreground="red")
            self.log(f"✓ {msg}")
        else:
            self.log(f"✗ {msg}")

    def refresh_pose(self):
        pose = get_current_pose()
        if pose:
            pose_str = f"[{pose[0]:.3f}, {pose[1]:.3f}, {pose[2]:.3f}, {pose[3]:.3f}, {pose[4]:.3f}, {pose[5]:.3f}]"
            self.pose_label.config(text=pose_str)
            self.log(f"Current pose: {pose_str}")
        else:
            self.log("Could not retrieve current pose")
            messagebox.showerror("Error", "Could not get current pose")

    def save_pick_pose(self):
        pose = get_current_pose()
        if pose:
            table = self.table_var.get()
            self.poses_data.setdefault("tables", {})
            self.poses_data["tables"].setdefault(table, {})
            self.poses_data["tables"][table]["pick_pose"] = pose
            if save_poses(self.poses_data):
                self.log(f"✓ Pick pose saved (Table {table}): {pose}")
                messagebox.showinfo("Success", f"Pick pose saved for Table {table}")
            else:
                self.log("✗ Failed to save pick pose")
                messagebox.showerror("Error", "Failed to save pose")
        else:
            messagebox.showerror("Error", "Could not get current pose")

    def save_safe_pick_pose(self):
        pose = get_current_pose()
        if pose:
            table = self.table_var.get()
            self.poses_data.setdefault("tables", {})
            self.poses_data["tables"].setdefault(table, {})
            self.poses_data["tables"][table]["safe_pick"] = pose
            if save_poses(self.poses_data):
                self.log(f"✓ Safe pick pose saved (Table {table}): {pose}")
                messagebox.showinfo("Success", f"Safe pick pose saved for Table {table}")
            else:
                self.log("✗ Failed to save safe pick pose")
                messagebox.showerror("Error", "Failed to save pose")
        else:
            messagebox.showerror("Error", "Could not get current pose")

    def save_place_pose(self):
        pose = get_current_pose()
        if pose:
            table = self.table_var.get()
            self.poses_data.setdefault("tables", {})
            self.poses_data["tables"].setdefault(table, {})
            self.poses_data["tables"][table]["place_pose"] = pose
            if save_poses(self.poses_data):
                self.log(f"✓ Place pose saved (Table {table}): {pose}")
                messagebox.showinfo("Success", f"Place pose saved for Table {table}")
            else:
                self.log("✗ Failed to save place pose")
                messagebox.showerror("Error", "Failed to save pose")
        else:
            messagebox.showerror("Error", "Could not get current pose")

    def save_safe_place_pose(self):
        pose = get_current_pose()
        if pose:
            table = self.table_var.get()
            self.poses_data.setdefault("tables", {})
            self.poses_data["tables"].setdefault(table, {})
            self.poses_data["tables"][table]["safe_place"] = pose
            if save_poses(self.poses_data):
                self.log(f"✓ Safe place pose saved (Table {table}): {pose}")
                messagebox.showinfo("Success", f"Safe place pose saved for Table {table}")
            else:
                self.log("✗ Failed to save safe place pose")
                messagebox.showerror("Error", "Failed to save pose")
        else:
            messagebox.showerror("Error", "Could not get current pose")

    def view_poses(self):
        self.log("=== Saved Poses ===")
        table = self.table_var.get() if hasattr(self, 'table_var') else '1'
        tables = self.poses_data.get('tables', {})
        if table in tables:
            t = tables[table]
            self.log(f"Table {table} - Pick: {t.get('pick_pose')}")
            self.log(f"Table {table} - Safe Pick: {t.get('safe_pick')}")
            self.log(f"Table {table} - Place: {t.get('place_pose')}")
            self.log(f"Table {table} - Safe Place: {t.get('safe_place')}")
        else:
            self.log(f"Table {table} not configured")

        self.log(f"Num Boxes: {self.poses_data.get('num_boxes')}")
        self.log(f"Box Height: {self.poses_data.get('box_height')}")
        self.log(f"Approach Offset: {self.poses_data.get('approach_offset')}")
        self.log(f"Normal Speed (vel): {self.poses_data.get('vel')}")
        self.log(f"Slow Speed (vel_slow): {self.poses_data.get('vel_slow')}")

    def save_parameters(self):
        """Save all stacking parameters to poses file."""
        try:
            self.poses_data["num_boxes"] = self.num_boxes_var.get()
            self.poses_data["box_height"] = self.box_height_var.get()
            self.poses_data["approach_offset"] = self.offset_var.get()
            self.poses_data["vel"] = self.vel_var.get()
            self.poses_data["vel_slow"] = self.vel_slow_var.get()
            
            if save_poses(self.poses_data):
                self.log("✓ Parameters saved successfully")
                messagebox.showinfo("Success", "Parameters saved!")
            else:
                self.log("✗ Failed to save parameters")
                messagebox.showerror("Error", "Failed to save parameters")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid parameters: {str(e)}")

    def start_stacking(self):
        if not robot:
            messagebox.showerror("Error", "Robot not connected")
            return

        try:
            num_boxes = self.num_boxes_var.get()
            box_height = self.box_height_var.get()
            approach_offset = self.offset_var.get()
            vel_normal = self.vel_var.get()
            vel_slow = self.vel_slow_var.get()

            # select poses from currently selected table
            table = self.table_var.get() if hasattr(self, 'table_var') else '1'
            tables = self.poses_data.get('tables', {})
            tbl = tables.get(table, {})
            pick_pose = tbl.get('pick_pose')
            place_pose = tbl.get('place_pose')
            safe_pick = tbl.get('safe_pick')
            safe_place = tbl.get('safe_place')

            self.log(f"Starting stacking: {num_boxes} boxes, height {box_height} mm")
            self.log(f"Speed: normal={vel_normal}, slow={vel_slow}")

            # Run in background thread
            def stacking_thread():
                run_stacking_sequence(pick_pose, place_pose, safe_pick, safe_place, num_boxes, box_height, approach_offset, self.log, vel_normal, vel_slow)

            thread = threading.Thread(target=stacking_thread, daemon=True)
            thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Invalid parameters: {str(e)}")

    def go_home_action(self):
        """Move robot to home pose in background thread."""
        if not robot:
            messagebox.showerror("Error", "Robot not connected")
            return
        
        def home_thread():
            if go_home(home_pose):
                self.log("✓ Moved to home position")
            else:
                self.log("✗ Failed to move to home position (stopped or paused)")
        
        thread = threading.Thread(target=home_thread, daemon=True)
        thread.start()

    def log(self, message):
        self.output_text.insert(tk.END, f"{message}\n")
        self.output_text.see(tk.END)
        self.root.update()