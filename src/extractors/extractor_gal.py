# src/extractors/extractor_gal.py
import sys
import re
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from common.errors import (
    error_msg,
    check_postal_code,
    check_coords,
    register_rejection,
    register_repair,
)
from common.dependencies import get_api_data, save_transformed_to_json, transformed_data_to_database
from common.validators import clean_invalid_email

SOURCE_TAG = "gal"

DD_REGEX = re.compile(r"^[+-]?\d+(\.\d+)?$")


# Si es ddm lo transforma a dd, si es dd no hace nada y si no devuelve None
def ddm_to_dd_or_pass(s: str) -> float | None:
    s = s.strip()
    # Esto es necesario pq el simbolo º da error
    ddm_extract_pattern = r"^([+-]?\d+)[\u00B0\s]+(\d+\.?\d*)['\"]?$"
    match_groups = re.match(ddm_extract_pattern, s)
    
    if match_groups:
        try:
            degrees = float(match_groups.group(1))
            minutes = float(match_groups.group(2))
            # Para coordenadas negativas, los minutos también deben ser negativos
            if degrees < 0:
                return round(degrees - minutes / 60, 6)
            else:
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
        "CÓDIGO POSTAL": "codigo_postal",
        "COORDENADAS GMAPS": "coordenadas", # Clave temporal para procesar coords
        "HORARIO": "horario",
        "CORREO ELECTRÓNICO": "contacto",
        "TELÉFONO": "telefono",
        "SOLICITUDE DE CITA PREVIA": "url",
        "CONCELLO": "l_nombre",
        "PROVINCIA": "p_nombre"
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
            
            if not check_coords(
                e_nombre,
                lat,
                lon,
                source=SOURCE_TAG,
                localidad=transformed.get("l_nombre"),
            ):
                return None
            
            transformed["latitud"] = lat # Clave nueva con datos transformados
            transformed["longitud"] = lon
        else:
            register_rejection(
                SOURCE_TAG,
                e_nombre,
                transformed.get("l_nombre"),
                "Coordenadas con formato no reconocible",
            )
            return None

    cod_postal = str(transformed.get("codigo_postal", None))
    if cod_postal:
        transformed["p_cod"] = cod_postal[:2]
    else:
        error_msg(e_nombre, ["codigo_postal"])
        transformed["p_cod"] = None
        
    if not check_postal_code(
        e_nombre,
        cod_postal,
        source=SOURCE_TAG,
        localidad=transformed.get("l_nombre"),
    ):
        return None
        
    if not transformed.get("contacto"):
        telefono = transformed.get("telefono", "")
        if telefono:
            transformed["contacto"] = telefono
            register_repair(
                SOURCE_TAG,
                e_nombre,
                transformed.get("l_nombre"),
                "Campo de contacto vacío",
                "Sustituido por número de teléfono",
            )
        else:
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


def transform_gal_data(data_list: list[dict]) -> list[dict]:
    transformed_data = []
    stats_trans = {"total": 0, "valid": 0, "invalid": 0}

    for record in data_list:
        stats_trans["total"] += 1
        res = transform_gal_record(record)
        if res:
            transformed_data.append(res)
            stats_trans["valid"] += 1
        else:
            stats_trans["invalid"] += 1
            
    print(f"Transformación GAL: Total {stats_trans['total']}, Válidos {stats_trans['valid']}, Inválidos {stats_trans['invalid']}")
    return transformed_data


if __name__ == "__main__":
    # Recupera datos de la API
    data_list = get_api_data("gal")

    # Transforma datos
    transformed_data = transform_gal_data(data_list)

    # Guarda datos transformados a json (solo debug)
    save_transformed_to_json(transformed_data, "gal")

    # Sube datos a la BD (Independiente de lo anterior)
    transformed_data_to_database(transformed_data, "gal")