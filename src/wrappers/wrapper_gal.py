# src/wrappers/wrapper_gal.py
import csv
from pathlib import Path

def csvtojson() -> list:
    csv_path = (
        Path(__file__).resolve()
        .parent.parent.parent / "data" / "Estacions_ITV.csv"
    )
    if not csv_path.exists():
        raise FileNotFoundError(f"Estacions_ITV.csv not found at: {csv_path}")

    with csv_path.open("r", encoding="UTF-8") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        data = [row for row in reader]
    return data