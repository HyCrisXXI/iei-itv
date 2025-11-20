# src/extractors/extractor_cv.py
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))


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


def transform_cv_record(record: dict) -> dict:
    KEY_MAPPING = {
        "Nº ESTACIÓN":   "e_cod",
        "MUNICIPIO":     "l_nombre",
        "TIPO ESTACIÓN": "tipo_estacion",
        "DIRECCIÓN":     "direccion",
        "C.POSTAL":      "cod_postal",
        "HORARIOS":      "horario",
        "CORREO":        "contacto",
        "PROVINCIA":     "p_nombre"
    }

    transformed = {}
    for old_key, new_key in KEY_MAPPING.items():
        if old_key in record:
            transformed[new_key] = record[old_key]

  
    cod_postal_string = str(transformed.pop("cod_postal", ""))
    transformed["p_cod"] = cod_postal_string[:2] if cod_postal_string else None

    correo = transformed.get("contacto")
    transformed["url"] = extract_domain_from_email(correo)

    return transformed

if __name__ == "__main__":
    data_list = jsontojson()
    transformed_data = [transform_cv_record(record) for record in data_list]
    out_path = Path(__file__).resolve().parent / "cv.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(transformed_data, jsonfile, indent=4, ensure_ascii=False)