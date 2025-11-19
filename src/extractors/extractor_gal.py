# src/extractors/extractor_gal.py
import sys
import re
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from wrappers.wrapper_gal import csvtojson

DD_REGEX = re.compile(r"^[+-]?\d+(\.\d+)?$")

def ddm_to_dd_or_pass(s: str) -> float | None:
    s = s.strip()
    # Esto es necesario pq el simbolo º da error
    ddm_extract_pattern = r"^([+-]?\d+)[\u00B0\s]+(\d+\.\d+)['\"]?$"
    match_groups = re.match(ddm_extract_pattern, s)
    
    if match_groups:
        try:
            degrees = float(match_groups.group(1))
            minutes = float(match_groups.group(2))
            return round(degrees + minutes / 60, 6)
        except ValueError:
            return None
    
    if DD_REGEX.fullmatch(s):
        try:
            return float(s)
        except ValueError:
            return None
    return None

    
def process_coordinate_pair(pair_string: str) -> tuple[float | None, float | None]:
    parts = [p.strip() for p in pair_string.split(',', 1)]
    
    if len(parts) != 2:
        return None, None
    
    lat = ddm_to_dd_or_pass(parts[0])
    lon = ddm_to_dd_or_pass(parts[1])
    
    return lat, lon

def transform_itv_record(record: dict) -> dict:
    KEY_MAPPING = {
        "NOME DA ESTACIÓN": "e_nombre",
        "ENDEREZO": "direccion",
        "CONCELLO": "l_nombre",
        "CÓDIGO POSTAL": "cod_postal",
        "PROVINCIA": "p_nombre",
        "HORARIO": "horario",
        "SOLICITUDE DE CITA PREVIA": "url",
        "CORREO ELECTRÓNICO": "contacto",
        "COORDENADAS GMAPS": "coordenadas" # Clave temporal para procesar coords
    }
    
    transformed = {} # Claves estandarizadas
    for old_key, new_key in KEY_MAPPING.items():
        if old_key in record:
            transformed[new_key] = record[old_key]
    
    # Elimina clave original
    coord_string = transformed.pop("coordenadas", None)
    
    if coord_string:
        parts = [p.strip() for p in coord_string.split(',', 1)]
        
        if len(parts) == 2:
            lat = ddm_to_dd_or_pass(parts[0]) # Función de conversión DDM/DD
            lon = ddm_to_dd_or_pass(parts[1])
            
            transformed["lat"] = lat # Clave nueva con datos transformados
            transformed["lon"] = lon
        else:
            transformed["lat"] = None
            transformed["lon"] = None
    
    cod_postal_string = transformed.pop("cod_postal", None)
    transformed["p_cod"] = cod_postal_string[:2] if cod_postal_string else None
    
    return transformed

if __name__ == "__main__":
    data_list = csvtojson()
    transformed_data = [transform_itv_record(record) for record in data_list]
    out_path = Path(__file__).resolve().parent / "gal.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(transformed_data, jsonfile, indent=4, ensure_ascii=False)