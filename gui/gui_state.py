class GUI_State:
    def __init__(self):
        """
        Initializes default GUI state values for navigation, telemetry, and inputs.
        args:
         - None
        return:
         - None: sets instance attributes with initial defaults.
        """
        self.navigation_section = "AMR"
        self.robot_pose = None
        self.camera_status = "OFF"
        self.selected_target = None
        self.nb_turn_in_place = 0
        self.dd_points = "Home"
        self.robot_pose = None
        self.battery_percentage = None
        self.robot_speed = 0
        
    def to_dict(self):
        """
        Converts the GUI state object into a serializable dictionary.
        args:
         - None
        return:
         - dict: dictionary representation of the current GUI state.
        """
        return {
            "navigation_section": self.navigation_section,
            "robot_pose": self.robot_pose,
            "camera_status": self.camera_status,
            "selected_target": self.selected_target,
            "nb_turn_in_place": self.nb_turn_in_place,
            "dd_points": self.dd_points,
            "robot_pose": self.robot_pose,
            "battery_percentage": self.battery_percentage,
            "robot_speed": self.robot_speed
        }

    @staticmethod
    def from_dict(data):
        """
        Reconstructs a GUI_State instance from a dictionary of attribute values.
        args:
         - data: dict mapping state field names to their values.
        return:
         - GUI_State: a new state object populated from the dictionary.
        """
        st = GUI_State()
        for k, v in data.items():
            setattr(st, k, v)
        return st