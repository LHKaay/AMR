# main.py
from gui import create_gui, custom_css

if __name__ == "__main__":
    demo = create_gui()
    demo.launch(css=custom_css)