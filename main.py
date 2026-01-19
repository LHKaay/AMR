from utils import load_config
from gui import run_gui

if __name__ == "__main__":
    amrs = load_config()
    run_gui(amrs)