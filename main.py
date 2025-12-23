import time
import rest_api
from msis_amr import MSIS_AMR_Controller

def main():
    # 1. Connection
    print("=== MSIS AMR Control System ===")
    ip_address = "192.168.0.132"
    
    # We use connect_to_amr helper to initialize/register the robot
    robot = rest_api.connect_to_amr(ip_address)
    
    if not robot:
        print("Could not connect to robot. Exiting.")
        return

    # 2. Initialize Controller
    controller = MSIS_AMR_Controller(robot)

    # 3. Map Operations
    print("\n--- Map Operations ---")
    
    # [MODIFIED] Use method directly: robot.get_map_explore()
    raw_map = robot.get_map_explore() 
    
    if raw_map:
        grid, meta = controller.create_map_from_data(raw_map)
        print(f"Map Loaded: {meta['width']}x{meta['height']} pixels")
        
        # Save Initial Map
        controller.save_map_as_svg("initial_map.svg")
        
        # Edit Map (Add obstacle on local copy)
        controller.edit_map_add_obstacle(x=1.0, y=0.5, radius_pixels=10)
        
        # Add Real Forbidden Area to Robot
        controller.add_custom_obstacle_to_robot(0.0, 0.0, 0.5, 0.5)
    else:
        print("Failed to get map data.")

    # 4. Movement Operations
    print("\n--- Movement Operations ---")
    
    # [MODIFIED] Use method directly: robot.get_pose()
    start_pose = robot.get_pose()
    print(f"Start Pose: {start_pose}")

    # A. Move Straight (Relative)
    # controller.move_straight(distance_meters=1.0)
    # controller.wait_until_idle()

    # B. Move Rectangular (Orthogonal to target 2.0, 2.0)
    # Assumes robot is at (0,0) roughly
    controller.move_rectangular_path(target_x=2.0, target_y=1.0)
    
    # C. Multi-point Path
    waypoints = [
        {'x': 0.0, 'y': 0.0},
        {'x': 1.0, 'y': 1.0},
        {'x': 0.0, 'y': 0.0}
    ]
    controller.move_multi_point(waypoints)

    # 5. Finalize
    print("\n--- Finalizing ---")
    # Display path on map and save result
    controller.display_path_on_map()
    controller.save_map_as_svg("path_map.svg")
    
    print("Done.")

if __name__ == "__main__":
    main()