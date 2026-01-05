# 🤖 MSIS AMR Control Studio

**MSIS AMR Control Studio** is a Python-based software designed for the integrated management and control of **Autonomous Mobile Robots (AMR)** via a web interface. It utilizes **Gradio** to provide an intuitive UI and employs **Folium/Leaflet** for real-time map visualization and editing capabilities.

---

## ✨ Key Features

### 1. Robot Connection & Status Monitoring
* **Multi-Robot Management**: Connect to and switch between multiple robots via IP address.
* **Status Dashboard**: Real-time monitoring of robot Pose, Battery status, Health check (Error code inspection and clearing), and Connection status.
* **Power Management**: Remote robot shutdown.

### 2. Real-time Map Visualization
* **Map Rendering**: Real-time streaming and display of SLAM-generated Grid Maps.
* **LIDAR Data**: Overlay of real-time robot LIDAR scan data (Rays/Points).
* **Path Display**: Visualization of the robot's movement trajectory and planned path.
* **Custom Icons**: Intuitive icon representation for Docks, POIs (Pins, Directional Arrows), Elevator scheduling points, etc.

### 3. Motion Control
* **Manual Control**: Movement (Forward/Backward/Left/Right) via virtual joystick buttons.
* **Point Navigation**: "Free Move" to a target destination by clicking on the map.
* **Virtual Track Navigation**: Precision driving modes based on virtual tracks (Strict/Priority).
* **Go Home**: Command to automatically return to the charging station.

### 4. Map Editing & Artifact Management
* **Virtual Lines/Tracks**:
    * Draw Straight Lines and Rectangular Lines (Rect Line).
    * **Bezier Curve Support**: Generate smooth curved tracks by connecting multiple points (Optimized with Batch creation).
* **Area Management**:
    * **Supported Types**: Forbidden, Elevator, Dangerous, Coverage, Maintenance, Sensor Disable, Restricted Area.
    * **Advanced Editing**: Support for **Rotation** and resizing after area creation.
    * **Property Settings**: UI for detailed attribute settings such as Dangerous Area (Speed limit), Sensor Disable (Toggle specific sensors), Elevator (Door direction), etc.
* **POI (Point of Interest) Management**:
    * Create POIs at the robot's current location or a clicked map location.
    * Edit POI Name, Type, Coordinates, and **Orientation (Yaw)**, or delete them.
    * Auto-correction of POI positions using the `Adjust` function.
* **Home Dock**: Register and delete charging stations.

### 5. Calibration
* **Align Axis**: Function to reset the map's coordinate axis based on the robot's current heading (set to 0 degrees).

---

## 📂 Project Structure

```text
MSIS_AMR/
│
├── gui.py              # [Main UI] Gradio interface layout and component definitions
├── gui_handlers.py     # [Controller] UI event handling and logic connection handlers
├── msis_amr.py         # [Service] Robot state management, data processing, Manager class
├── rest_api.py         # [Infrastructure] HTTP REST API communication wrapper (CRUD: Create, Read, Update, Delete)
├── gui_map_utils.py    # [Visualization] Folium/Leaflet-based map rendering and SVG icon utilities
│
├── map_icon/           # Folder for icons and logo images used in the UI
│   ├── msis_logo.png
│   └── dock.jpg
│
└── robot.db            # Local SQLite database for storing robot connection info
```

🛠️ Installation & Usage
1. Prerequisites
This project recommends a Python 3.8+ environment. Install the dependencies using the command below:

```Bash

pip install gradio requests numpy folium jinja2
```
2. How to Run
Execute the main script from the project root directory.
```Bash

# RUN Command
python main.py
```
(Note: Ensure your entry point is set correctly, e.g., if starting via gui.py, use python gui.py)

3. Accessing the Interface
Once running, access the control panel via the local URL displayed in the terminal.

URL Example: http://127.0.0.1:7860

## 📝 Changelog
**System Stability**
* Enhanced API communication exception handling (Fixed NoneType errors).

* Fixed coordinate calculation errors during Coverage Area creation.

**Visualization Enhancements**
* Improved visibility by applying SVG icons (Pins, Arrows).

* Added visualization for Forbidden Area Escape Distance and Elevator Area Door/Scheduling Points.

**New Features**
* Resolved path discontinuity issues using Batch Processing for Bezier Curves.

* Added support for Rotation when creating Rectangular Areas.

* Integrated POI creation (Click-based) and editing (including Yaw angle) features.

---
Developed by MSIS Lab. 
Mincheol Park