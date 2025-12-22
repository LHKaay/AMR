from gui.gui import demo
from gui.gui_schema import GUI_SCHEMA


if __name__ == "__main__":
    CSS = open(f"gui/{GUI_SCHEMA['css_file']}", encoding='utf-8').read()
    JS = open(f"gui/{GUI_SCHEMA['js_file']}", encoding='utf-8').read()

    demo.launch(css=CSS, js=JS)