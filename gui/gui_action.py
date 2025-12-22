import math
import time
import yaml
from msis_amr_motion import MSIS_PHOEBUS


with open("configs/config.yaml", 'r') as stream:
    try:
        # Use safe_load for security when loading from untrusted sources
        config = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)


Msis_AMR = MSIS_PHOEBUS(config['amr']['ip'], config['amr']['port'])

def shutdown_amr(state: dict):
    """
    Triggers an immediate shutdown of the AMR system via the motion client.
    args:
     - state: dict shared GUI state passed through unchanged.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.shutdown_amr()
    return state

def hibernate_amr(state: dict):
    """
    Sends the AMR into hibernation mode through the system API.
    args:
     - state: dict shared GUI state passed through unchanged.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.hibernate_amr()
    return state

def wakeup_amr(state: dict):
    """
    Wakes the AMR from hibernation using the system wake endpoint.
    args:
     - state: dict shared GUI state passed through unchanged.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.wakeup_amr()
    return state

def restart_amr(state: dict):
    """
    Restarts AMR modules through the system restart API call.
    args:
     - state: dict shared GUI state passed through unchanged.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.restart_amr()
    return state

def update_amr_info(state: dict):
    """
    Updates state with the latest pose, battery percentage, and speed telemetry values.
    args:
     - state: dict shared GUI state to populate with AMR telemetry.
    return:
     - dict: updated state including 'robot_pose', 'battery_percentage', and 'robot_speed'.
    """
    try:
        pose = Msis_AMR.get_robot_pose()
        state['robot_pose'] = f"{pose['x']:.2f}, {pose['y']:.2f}, {pose['yaw']:.2f}"

        battery = Msis_AMR.get_power_status()
        state['battery_percentage'] = battery['batteryPercentage']

        speed_response = Msis_AMR.get_robot_speed()
        speed = math.sqrt(round(speed_response['vx'],5)**2 + round(speed_response['vy'],5)**2)
        state['robot_speed'] = speed

    except Exception as e:
        state['robot_pose'] = "0, 0, 0"
        state['battery_percentage'] = "0"

    return state

def stop_amr_motion(state: dict):
    """
    Immediately stops any ongoing motion action on the AMR.
    args:
     - state: dict shared GUI state passed through unchanged.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.stop_motion_now()
    return state

def go_charge(state: dict):
    """
    Commands the AMR to navigate to and dock at the charging station.
    args:
     - state: dict shared GUI state passed through unchanged.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.go_charge()
    return state

def set_charge_station(state: dict):
    """
    Registers the current AMR position as the charging station location.
    args:
     - state: dict shared GUI state passed through unchanged.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.set_charge_station()
    return state

def turn_left(state: dict):
    """
    Rotates the AMR in place by +90 degrees to the left.
    args:
     - state: dict shared GUI state passed through unchanged.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.rotate_by_inPlace(90)
    return state

def turn_right(state: dict):
    """
    Rotates the AMR in place by -90 degrees to the right.
    args:
     - state: dict shared GUI state passed through unchanged.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.rotate_by_inPlace(-90)
    return state

def turn_back(state: dict):
    """
    Rotates the AMR in place by 180 degrees to face backward.
    args:
     - state: dict shared GUI state passed through unchanged.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.rotate_by_inPlace(180)
    return state

def update_state(state: dict, *args):
    """
    Updates a single key in the shared state using a key/value pair from args.
    args:
     - state: dict representing the shared GUI state to update.
     - *args: tuple expected as (key, value) specifying the state change.
    return:
     - dict: the modified state dictionary after applying the update.
    """
    print(f"Updating state: {args[0]} = {args[1]}")
    state[args[0]] = args[1]
    return state

def turn_in_place(state: dict):
    """
    Rotates the AMR in place by the angle stored in 'nb_turn_in_place'.
    args:
     - state: dict containing 'nb_turn_in_place' angle value in degrees.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.rotate_by_inPlace(state.get("nb_turn_in_place", 0))
    return state

def go_to_point(state: dict):
    """
    Navigates the AMR to a preconfigured point or home based on 'dd_points'.
    args:
     - state: dict containing 'dd_points' and configuration-driven positions.
    return:
     - dict: the same state dictionary without modification.
    """
    if state.get("dd_points") == 'Home':
        Msis_AMR.go_to(target_x=0, target_y=0, yaw=0, label=state.get("dd_points"))
    else:
        Msis_AMR.go_to(target_x=config['amr']['Middle_point']['x'], 
                       target_y=config['amr']['Middle_point']['y'],
                       yaw=config['amr'][f'{state.get("dd_points")}']['yaw'])
        time.sleep(5)
        Msis_AMR.go_to(target_x=config['amr'][f'{state.get("dd_points")}']['x'],
                       target_y=config['amr'][f'{state.get("dd_points")}']['y'],
                        yaw=config['amr'][f'{state.get("dd_points")}']['yaw'])

    return state

def go_by_distance(state: dict):
    """
    Moves the AMR a specified distance at a relative angle from current heading.
    args:
     - state: dict containing 'nb_angle' in degrees and 'nb_distance' in meters.
    return:
     - dict: the same state dictionary without modification.
    """
    Msis_AMR.go_by_distance(angle=state.get("nb_angle", 0), distance=state.get("nb_distance", 0))
    return state


GUI_ACTIONS = {
    "shutdown_amr": shutdown_amr,
    "hibernate_amr": hibernate_amr,
    "wakeup_amr": wakeup_amr,
    "restart_amr": restart_amr,
    "stop_amr_motion": stop_amr_motion,
    "go_charge": go_charge,
    "set_charge_station": set_charge_station,
    "turn_left": turn_left,
    "turn_right": turn_right,
    "turn_back": turn_back,
    "turn_in_place": turn_in_place,
    "update_state": update_state,
    "go_to_point": go_to_point,
    "update_amr_info": update_amr_info,
    "go_by_distance": go_by_distance
}