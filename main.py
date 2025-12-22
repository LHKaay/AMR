from MSIS_robot_control import *
from gui import RobotGUI
from tkinter import Tk
if __name__ == "__main__":
    root = tk.Tk()
    app = RobotGUI(root)
    root.mainloop()