# src/wrappers/wrapper_gal.py
import csv
import json
from pathlib import Path

def csvtojson():
    csv_path = (
        Path(__file__).resolve()
        .parent.parent.parent / "data" / "Estacions_ITV.csv"
    )
    if not csv_path.exists():
        raise FileNotFoundError(f"Estacions_ITV.csv not found at: {csv_path}")

    out_path = Path(__file__).resolve().parent / "gal.json"

    with csv_path.open("r", encoding="ISO-8859-1") as csvfile, out_path.open("w", encoding="utf8") as jsonfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        data = [row for row in reader]

        json.dump(data, jsonfile, ensure_ascii=False, indent=4)
csvtojson()