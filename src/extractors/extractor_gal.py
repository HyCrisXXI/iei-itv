# src/extractors/extractor_gal.py
import csv
import json

def csvtojson():
    with open("Estacions_ITV.csv", "r", encoding="ISO-8859-1") as csvfile, \
            open("estaciones_gal.json", "w", encoding="utf8") as jsonfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        data = [row for row in reader]

        json.dump(data, jsonfile, ensure_ascii=False, indent=4)
csvtojson()