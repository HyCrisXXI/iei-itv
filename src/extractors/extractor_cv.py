# src/extractors/extractor_cv.py
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from geopy.geocoders import Nominatim
import time
import re
import unicodedata


def jsontojson():
    json_path = (
        Path(__file__).resolve()
        .parent.parent.parent / "data" / "estaciones.json"
    )
    
    if not json_path.exists():
        raise FileNotFoundError(f"estaciones.json not found at: {json_path}")
    
    with json_path.open("r", encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)
    
    return data


def extract_domain_from_email(email: str) -> str | None:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1]


def limpiar_direccion(texto: str) -> str:
    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = texto.replace("'", "").replace('"', "")
    texto = re.sub(r"s[/\s]*n[º°]?", "sin numero", texto, flags=re.IGNORECASE)
    texto = texto.replace("I.T.V", "ITV")
    texto = texto.replace("·", " ")
    texto = texto.replace("ª", "a")
    texto = texto.replace("º", "o")
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def normalizar_direccion(record: dict) -> str | None:
    direccion = record.get("direccion", "")
    municipio = record.get("l_nombre", "")
    provincia = record.get("p_nombre", "")

    if not direccion:
        return None

    direccion = limpiar_direccion(direccion)
    municipio = limpiar_direccion(municipio)
    provincia = limpiar_direccion(provincia)

    return f"{direccion}, {municipio}, {provincia}, Espana"


geolocator = Nominatim(user_agent="extractor_cv")


def get_coords(direccion: str):
    if not direccion:
        return None, None

    try:
        loc = geolocator.geocode(direccion, timeout=10)
        time.sleep(1)
        if not loc:
            loc = geolocator.geocode({"q": direccion}, timeout=10)
            time.sleep(1)
        if loc:
            return loc.latitude, loc.longitude

    except Exception as e:
        print(f"Error geocodificando '{direccion}': {e}")

    return None, None


def transform_cv_record(record: dict) -> dict:
    KEY_MAPPING = {
        "TIPO ESTACIÓN": "tipo_estacion",
        "DIRECCIÓN":     "direccion",
        "C.POSTAL":      "codigo_postal",
        "HORARIOS":      "horario",
        "CORREO":        "contacto",
        "MUNICIPIO":     "l_nombre",
        "PROVINCIA":     "p_nombre"
    }

    transformed = {}
    for old_key, new_key in KEY_MAPPING.items():
        if old_key in record:
            transformed[new_key] = record[old_key]

  
    cod_postal_string = str(transformed.get("codigo_postal", ""))
    transformed["p_cod"] = cod_postal_string[:2] if cod_postal_string else None

    correo = transformed.get("contacto")
    transformed["url"] = extract_domain_from_email(correo)

    direccion = transformed.get("direccion")
    lat, lon = get_coords(direccion)
    transformed["lat"] = lat
    transformed["lon"] = lon

    return transformed

if __name__ == "__main__":
    data_list = jsontojson()
    transformed_data = [transform_cv_record(record) for record in data_list]
    out_path = Path(__file__).resolve().parent / "cv.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(transformed_data, jsonfile, indent=4, ensure_ascii=False)