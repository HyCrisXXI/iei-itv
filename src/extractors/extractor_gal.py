# src/extractors/extractor_gal.py
import sys
import re
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from database.models import TipoEstacion, Provincia, Localidad, Estacion
from database.session import get_db

from common.errors import error_msg, check_postal_code, check_coords
from common.dependencies import get_api_data, save_transformed_to_json
from common.db_storage import save_stations


DD_REGEX = re.compile(r"^[+-]?\d+(\.\d+)?$")

# Si es ddm lo transforma a dd, si es dd no hace nada y si no devuelve None
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

# Devuelve la coordenada separada en latitud (lat) y longitud (lon)
def process_coordinate_pair(pair_string: str) -> tuple[float | None, float | None]:
    parts = [p.strip() for p in pair_string.split(',', 1)]
    
    if len(parts) != 2:
        return None, None
    
    lat = ddm_to_dd_or_pass(parts[0])
    lon = ddm_to_dd_or_pass(parts[1])
    
    return lat, lon

# transforma los datos de cada estacion del json
def transform_gal_record(record: dict) -> dict:
    KEY_MAPPING = {
        "NOME DA ESTACIÓN": "nombre",
        "ENDEREZO": "direccion",
        "CONCELLO": "l_nombre",
        "CÓDIGO POSTAL": "codigo_postal",
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
    
    # Variable que sirve en esta función para mensajes de error
    e_nombre = transformed.get("nombre", None)
    
    # Elimina clave original
    coord_string = transformed.pop("coordenadas", None)
    if coord_string:
        parts = [p.strip() for p in coord_string.split(',', 1)]
        
        if len(parts) == 2:
            lat = ddm_to_dd_or_pass(parts[0]) # Función de conversión DDM/DD
            lon = ddm_to_dd_or_pass(parts[1])
            
            if not check_coords(e_nombre, lat, lon): return None
            
            transformed["latitud"] = lat # Clave nueva con datos transformados
            transformed["longitud"] = lon
        else:
            return None

    cod_postal = str(transformed.get("codigo_postal", None))
    if cod_postal:
        transformed["p_cod"] = cod_postal[:2]
    else:
        error_msg(e_nombre, ["codigo_postal"])
        transformed["p_cod"] = None
        
    if not check_postal_code(e_nombre, cod_postal):
        return None
        
    contacto = transformed.get("contacto", "")
    if not contacto:
        error_msg(e_nombre, ["contacto"])

    # Verificar otros campos requeridos para notificar si faltan
    required_fields = [
        "direccion", "codigo_postal", "latitud", "longitud", "horario", "contacto", "url"
    ]
    
    missing = [f for f in required_fields if not transformed.get(f)]
    if missing:
        error_msg(e_nombre, missing)
    
    transformed["tipo"] = "fija"  # Por defecto en Galicia

    return transformed

# Sube a la BD los datos transformados
def transformed_data_to_database(records: list):
    stats = save_stations(records, "gal")
    print(f"Inserción completa. Insertados: {stats['inserted']}, Omitidos: {stats['skipped']}, Errores: {len(stats['errors'])}")

if __name__ == "__main__":
    # Recupera datos de la API
    data_list = get_api_data("gal")

    # Normaliza datos a json (solo debug)
    transformed_data = [transform_gal_record(record) for record in data_list]
    save_transformed_to_json(transformed_data, "gal")

    # Sube datos a la BD (Independiente de lo anterior)
    transformed_data_to_database(transformed_data)