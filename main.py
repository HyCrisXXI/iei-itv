# main.py
from src.api.main import app
from src.gui import ITVSearchApp

if __name__ == "__main__":
    ITVSearchApp().run()