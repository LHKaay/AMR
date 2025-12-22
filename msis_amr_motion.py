import math
from rest_api import PLAIN_API
from utils.util import compute_target_pose

class MSIS_PHOEBUS:
    def __init__(self, ip="", port=80):
        """
        Initializes the AMR motion client with a REST API endpoint.
        args:
         - ip: string IP address of the AMR controller.
         - port: integer TCP port for the AMR controller.
        return:
         - None: constructs the client and stores the API instance.
        """
        self.api = PLAIN_API(ip, port)

    def shutdown_amr(self):
        """
        Sends a shutdown command to the AMR for immediate power off.
        args:
         - None
        return:
         - dict or None: API response payload or None on error.
        """
        payload = {
            "shutdown_time_interval": 0,
            "restart_time_interval": 0
        }
        return self.api._post("/api/core/system/v1/power/:shutdown", payload)
    
    def hibernate_amr(self):
        """
        Puts the AMR into hibernate mode via the system API.
        args:
         - None
        return:
         - dict or None: API response payload or None on error.
        """
        return self.api._post("/api/core/system/v1/power/:hibernate")
    
    def wakeup_amr(self):
        """
        Wakes the AMR from hibernation using the system API endpoint.
        args:
         - None
        return:
         - dict or None: API response payload or None on error.
        """
        return self.api._post("/api/core/system/v1/power/:wakeup")
    
    def restart_amr(self):
        """
        Restarts the AMR modules through the system restart endpoint.
        args:
         - None
        return:
         - dict or None: API response payload or None on error.
        """
        return self.api._post("/api/core/system/v1/power/:restartmodule")

    def get_power_status(self, _print=False):
        """
        Retrieves the current power and battery status of the AMR.
        args:
         - _print: bool flag to print the response for debugging.
        return:
         - dict or None: power status information or None on error.
        """
        response = self.api._get("/api/core/system/v1/power/status")
        if _print: print(response)
        return response

    def get_robot_speed(self, _print=False):
        """
        Fetches the current robot speed vector from the motion API.
        args:
         - _print: bool flag to print the response for debugging.
        return:
         - dict or None: speed data including components or None on error.
        """
        response = self.api._get("/api/core/motion/v1/speed")
        if _print: print(response)
        return response

    def get_robot_pose(self, _print=False):
        """
        Obtains the current robot pose (x, y, yaw) from localization.
        args:
         - _print: bool flag to print the response for debugging.
        return:
         - dict or None: pose information or None on error.
        """
        response = self.api._get("/api/core/slam/v1/localization/pose")
        if _print: print(response)
        return response

    def get_action_status(self, action_id, _print=False):
        """
        Queries the status of a specific motion action by identifier.
        args:
         - action_id: identifier string of the action to query.
         - _print: bool flag to print the response for debugging.
        return:
         - dict or None: action status details or None on error.
        """
        response = self.api._get(f"/api/core/motion/v1/actions/{action_id}")
        if _print: print(response)
        return response

    def stop_motion_now(self):
        """
        Immediately stops the current motion action if one is running.
        args:
         - None
        return:
         - dict or None: API response indicating stop result or None on error.
        """
        return self.api._delete("/api/core/motion/v1/actions/:current")
    
    def set_charge_station(self):
        """
        Registers the current location as the designated charge station.
        args:
         - None
        return:
         - dict or None: API response payload or None on error.
        """
        payload = {
            "metadata": {
                "display_name": "string"
            }
        }
        return self.api._post("/api/core/slam/v1/homedocks/:register", payload)
    
    def go_to(self, target_x, target_y, yaw=None, label="go_to"): 
        """
        Commands the AMR to move to a target coordinate with optional yaw.
        args:
         - target_x: float X-axis target position (meters).
         - target_y: float Y-axis target position (meters).
         - yaw: float target yaw in degrees or None to omit orientation.
         - label: string label for action tagging purposes.
        return:
         - None: posts a motion action, no direct return value.
        """
        if yaw is None:  
            payload = {
                "action_name": "slamtec.agent.actions.MoveToAction",
                "options": {
                    "target": {"x": target_x, "y": target_y, "z": 0},
                    "move_options": {
                        "mode": 0,
                        "acceptable_precision": 0.0001,
                        "fail_retry_count": 0,
                        "flags": ["precise","with_yaw"],
                        "speed_ratio": 1.0,
                    },
                },
            }
        else:
            payload = {
                "action_name": "slamtec.agent.actions.MoveToAction",
                "options": {
                    "target": {"x": target_x, "y": target_y, "z": 0},
                    "move_options": {
                        "mode": 0,
                        "acceptable_precision": 0.0001,
                        "fail_retry_count": 0,
                        "speed_ratio": 1.0,
                        "flags": ["precise","with_yaw"],
                        "yaw": math.radians(yaw)
                    },
                },
            }
            
        self.api._post("/api/core/motion/v1/actions", payload)

    def go_by_distance(self, angle, distance, label="go_by_distance"):
        """
        Moves the AMR by a distance at a given relative angle from current pose.
        args:
         - angle: float relative heading in degrees from current yaw.
         - distance: float distance to travel in meters.
         - label: string label for action tagging purposes.
        return:
         - None: submits a MoveTo action based on computed target pose.
        """
        current_pose = self.get_robot_pose()
        target_pose = compute_target_pose(angle, current_pose, distance)

        payload = {
            "action_name": "slamtec.agent.actions.MoveToAction",
            "options": {
                "target": {"x": target_pose['x'], "y": target_pose['y'], "z": 0},
                "move_options": {
                    "mode": 0,
                    "acceptable_precision": 0.1,
                    "fail_retry_count": 0,
                    "speed_ratio": 1.0,
                },
            },
        }
        self.api._post("/api/core/motion/v1/actions", payload)
    
    def rotate_by_inPlace(self, deg=0):
        """
        Rotates the AMR in place by a relative angle in degrees.
        args:
         - deg: float relative rotation angle in degrees.
        return:
         - None: posts a rotation action, no direct return value.
        """
        payload = {"action_name": "slamtec.agent.actions.RotateAction", 
            "options": {
                "angle": math.radians(deg)
            }
        }

        self.api._post("/api/core/motion/v1/actions", payload)

    def rotate_to_inPlace(self, deg=0, unit='deg'):
        """
        Rotates the AMR in place to an absolute orientation.
        args:
         - deg: float target orientation value (degrees or radians).
         - unit: string specifying 'deg' for degrees or 'rad' for radians.
        return:
         - None: posts a rotate-to action, no direct return value.
        """
        payload = {"action_name": "slamtec.agent.actions.RotateToAction", 
            "options": {
                "angle": math.radians(deg) if unit=='deg' else deg
            }
        }

        self.api._post("/api/core/motion/v1/actions", payload)

    def go_charge(self):
        """
        Commands the AMR to return to and dock at the charge station.
        args:
         - None
        return:
         - None: posts a go-home docking action, no direct return value.
        """
        payload = {
            "action_name": "slamtec.agent.actions.GoHomeAction",
            "options": {
                "flags": "dock",
                "back_to_landing": True,
                "charging_retry_count": 2,
                "move_options": {"mode": 0},
            },
        }
        self.api._post("/api/core/motion/v1/actions", payload)
