# src/wrappers/wrapper_cv.py
import json
from pathlib import Path

def jsontojson():
    json_path = (
        Path(__file__).resolve()
        .parent.parent.parent / "data" / "estaciones.json"
    )