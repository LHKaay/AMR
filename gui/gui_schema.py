import gradio as gr

GUI_SCHEMA = {
    "css_file": "assest/style.css",
    "js_file": "assest/main_js.js",
    
    "navigation": [
        {"component": gr.Button, "name": "btn_AMR", "props": {"value": "AMR"},
            "click": {
                "fn": "update_state",
                "inputs": {"navigation_section":"AMR"},
                "outputs": []
            }
        },
        {"component": gr.Button, "name": "btn_Map", "props": {"value": "Map"},
            "click": {
                "fn": "update_state",
                "inputs": {"navigation_section":"Map"},
                "outputs": []
            }
        },
        {"component": gr.Button, "name": "btn_Camera", "props": {"value": "Camera"},
            "click": {
                "fn": "update_state",
                "inputs": {"navigation_section":"Camera"},
                "outputs": []
            }
        },
        {"component": gr.Button, "name": "btn_Arm", "props": {"value": "Arm"},
            "click": {
                "fn": "update_state",
                "inputs": {"navigation_section":"Arm"},
                "outputs": []
            }
        },
    ],

    "logo": {
        "component": gr.Image, "name": "logo_img",
        "props": {
            "value": "gui/assest/MSIS_AMR_ControlStudio_1linelogo.png",
            "height": 45,
            "show_label": False,
            "interactive": False,
            "buttons": [],
            "format":"png"
        }
    },

    "general_controls":[
        {"name": "btn_stop_AMR",
            "component": gr.Button, 
            "props": {"value": "Stop AMR 🛞", "variant": "stop"},
            "fn": "stop_amr_motion"
        },
        {"name": "btn_stop_arm",
            "component": gr.Button, 
            "props": {"value": "Stop Arm 🦾", "variant": "stop"},
            "fn": "stop_amr_motion"
        },
        {"name": "robot_speed",
            "component": gr.Slider,
            "props": {"value": 0, 
                      "minimum": 0, 
                      "maximum": 1.5,
                      "label": "Robot Speed (m/s)", 
                      "interactive": False,
                      "buttons": []},
            "fn": "update_state"
        }
    ],

    "amr_controls":[
        {"System Controls":[
            {"name": "btn_shutdown_amr",
                "component": gr.Button,
                "props": {"value": "Shutdown AMR"},
                "fn": "shutdown_amr"
            },
            {"name": "btn_hibernate_amr",
                "component": gr.Button,
                "props": {"value": "Hibernate AMR"},
                "fn": "hibernate_amr"
            },
            {"name": "btn_wake_amr",
                "component": gr.Button,
                "props": {"value": "Wake AMR up"},
                "fn": "wakeup_amr"
            },
            {"name": "btn_restart_amr",
                "component": gr.Button,
                "props": {"value": "Restart AMR"},
                "fn": "restart_amr"
            }
        ]},
        {"Charge options":[
            {"name": "btn_set_charge_station",
                "component": gr.Button,
                "props": {"value": "Set Charge Station"},
                "fn": "set_charge_station"
            },
            {"name": "btn_go_charge",
                "component": gr.Button,
                "props": {"value": "Go to Charge"},
                "fn": "go_charge"
            }
        ]},
        {"Move by distance":[
            {"name": "nb_distance",
                "component": gr.Number,
                "props": {"label": "Distance (m)", 
                        "placeholder": "Enter distance in m", 
                        "visible": True, "interactive": True},
                "fn": "update_state"
            },
            {"name": "nb_angle",
                "component": gr.Number,
                "props": {"label": "Angle (degrees)", 
                        "placeholder": "Enter angle in degrees", 
                        "visible": True, "interactive": True},
                "fn": "update_state"
            },
            {"name": "btn_go_by_distance",
                "component": gr.Button,
                "props": {"value": "Go by Distance ▶️"},
                "fn": "go_by_distance"
            }
        ]},
        {"Turn options":[
            {"name": "btn_turn_left",
                "component": gr.Button,
                "props": {"value": "Turn Left ⬅️"},
                "fn": "turn_left"
            },
            {"name": "btn_turn_right",
                "component": gr.Button,
                "props": {"value": "Turn Right ➡️"},
                "fn": "turn_right"
            },
            {"name": "btn_turn_back",
                "component": gr.Button,
                "props": {"value": "Turn Back ⬆️"},
                "fn": "turn_back"
            },
            {"name": "nb_turn_in_place",
                "component": gr.Number,     
                "props": {"label": "Angle (degrees)", 
                        "placeholder": "Enter angle in degrees", 
                        "visible": True, "interactive": True},
                "fn": "update_state"
            },
            {"name": "btn_turn_in_place",
                "component": gr.Button,
                "props": {"value": "Turn In Place 🔄"},
                "fn": "turn_in_place"
            },
        ]},
        {"Move to Point Options":[
            {"name": "dd_points",
                "component": gr.Dropdown    ,
                "props": {"value": "Home",
                    "choices": ["Home", "Table1", "Table2", "Table2_side"], 
                    "label": "Points", 
                    "visible": True, 
                    "interactive": True},
                "fn": "update_state"
            },
            {"name": "btn_go_to_point",
                "component": gr.Button,
                "props": {"value": "Go To Point"},
                "fn": "go_to_point"
            }
        ]},
    ],
}
