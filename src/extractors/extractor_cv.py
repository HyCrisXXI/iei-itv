# src/extractors/extractor_cv.py
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from wrappers.wrapper_cv import jsontojson

if __name__ == "__main__":
    data_list = jsontojson()
    out_path = Path(__file__).resolve().parent / "cv.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(data_list, jsonfile, indent=4, ensure_ascii=False)