# src/extractors/extractor_cat.py
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from wrappers.wrapper_cat import xmltojson

if __name__ == "__main__":
    data_list = xmltojson()
    out_path = Path(__file__).resolve().parent / "cat.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(data_list, jsonfile, indent=4, ensure_ascii=False) # minify: indent=None, separators=(",", ":")