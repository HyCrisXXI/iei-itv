# src/extractors/extractor_cat.py
import re
import sys
import xml.etree.ElementTree as ET

from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from common.dependencies import get_api_data, save_transformed_to_json, transformed_data_to_database
from common.errors import error_msg
from common.validators import clean_invalid_email

provinciaCat = ["Tarragona", "Lleida", "Girona", "Barcelona"]

cpCat = ["43", "25", "17", "08"]

mappingProvincia = {
    "08": "Barcelona",
    "17": "Girona",
    "25": "Lleida",
    "43": "Tarragona",
}

POINT_RE = re.compile(r"POINT\s*\(\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*\)", re.IGNORECASE)


def _extract_value(value):
    if isinstance(value, dict):
        if value.get("text"):
            return value["text"]
        if value.get("url"):
            return value["url"]
    return value


def _normalize_coordinate(value, *, is_latitude: bool) -> float | None:
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip().replace(",", ".")
        if not value:
            return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    limit = 90.0 if is_latitude else 180.0
    if -limit <= number <= limit:
        return round(number, 6)

    fallback = None
    for factor in (1_000_000, 100_000, 10_000, 1_000, 100):
        scaled = number / factor
        if -limit <= scaled <= limit:
            valid_lat = abs(scaled) >= 30.0 if is_latitude else True
            valid_lon = (0.3 <= abs(scaled) <= 10.0) if not is_latitude else True
            if valid_lat and valid_lon:
                return round(scaled, 6)
            if fallback is None:
                fallback = scaled
    if fallback is not None:
        return round(fallback, 6)
    return None


def _parse_wkt_point(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    match = POINT_RE.search(value)
    if not match:
        return None, None
    try:
        lon = float(match.group(1))
        lat = float(match.group(2))
    except ValueError:
        return None, None
    return lon, lat


def _coordinates_from_record(record: dict) -> tuple[float | None, float | None]:
    lat = _normalize_coordinate(record.get("lat"), is_latitude=True)
    lon = _normalize_coordinate(record.get("long"), is_latitude=False)

    if lat is None or lon is None:
        lon_raw, lat_raw = _parse_wkt_point(record.get("geocoded_column"))
        if lon is None:
            lon = _normalize_coordinate(lon_raw, is_latitude=False)
        if lat is None:
            lat = _normalize_coordinate(lat_raw, is_latitude=True)
    return lat, lon


def _province_code_from_postal(postal) -> str | None:
    if not postal:
        return None
    digits = "".join(ch for ch in str(postal) if ch.isdigit())
    if len(digits) >= 2:
        return digits[:2]
    
    return None


def transform_cat_record(record: dict) -> dict:
    KEY_MAPPING = {
        "denominaci": "nombre",
        "adre_a": "direccion",
        "cp": "codigo_postal",
        "lat": "latitud",
        "long": "longitud",
        "horari_de_servei": "horario",
        "correu_electr_nic": "contacto",
        "web": "url",
        "municipi": "l_nombre",
        "serveis_territorials": "p_nombre"
    }
    
    transformed = {} # Claves estandarizadas
    for old_key, new_key in KEY_MAPPING.items():
        value = _extract_value(record.get(old_key))
        if value is not None:
            transformed[new_key] = value

    transformed["tipo"] = "fija"

    # Limpiar emails inválidos (ej: "itv@" sin dominio) a None
    contacto = transformed.get("contacto")
    transformed["contacto"] = clean_invalid_email(contacto)
    
    # Si no hay contacto válido, usar URL como fallback
    if not transformed.get("contacto"):
        transformed["contacto"] = transformed.get("url")

    lat, lon = _coordinates_from_record(record)
    transformed["latitud"] = lat
    transformed["longitud"] = lon

    codigo_postal = transformed.get("codigo_postal")
    if codigo_postal is not None:
        codigo_postal = str(codigo_postal).strip()
        transformed["codigo_postal"] = codigo_postal or None
    transformed["p_cod"] = _province_code_from_postal(codigo_postal)
    
    # --- Validaciones unificadas ---
    est_name = transformed.get("nombre")
    p_code = transformed.get("p_cod")
    
    # 1. Validar Código Postal en Cataluña
    if p_code not in cpCat:
        error_msg(est_name or "Desconocida", [f"codigo_postal ({p_code}) fuera de rango CAT"])
        return None 

    # 2. Comprobar coincidencia entre Provincia y Código Postal
    nom_prov = transformed.get("p_nombre")
    
    if mappingProvincia.get(p_code) != nom_prov:
        if p_code in cpCat:
            transformed["p_nombre"] = mappingProvincia[p_code]
        else:
            error_msg(est_name or "Desconocida", [f"Provincia ({nom_prov}) no coincide con código postal ({p_code})"])
            return None

    # 3. Validar Nombre Provincia
    prov_name = transformed.get("p_nombre")
    if prov_name not in provinciaCat:
        if p_code in cpCat:
            prov_name = mappingProvincia[p_code]
            transformed["p_nombre"] = prov_name
        else:
            error_msg(est_name or "Desconocida", ["p_nombre"])
            return None
            
    if not prov_name:
        error_msg(est_name or "Desconocida", ["Provincia no identificada"])
        return None

    # Ajuste final de claves para la función de guardado común
    transformed["nombre"] = "ITV " + (est_name or "")
    
    # Validar campos requeridos

    required_fields = [
        "direccion", "codigo_postal", "latitud", "longitud", "horario", "contacto", "url"
    ]
    missing = [f for f in required_fields if not transformed.get(f)]
    if missing:
        error_msg(transformed["nombre"], missing)
        
    return transformed


def transform_cat_data(data_list: list) -> list:
    transformed_data = []
    stats_trans = {"total": 0, "valid": 0, "invalid": 0}

    for record in data_list:
        stats_trans["total"] += 1
        res = transform_cat_record(record)
        if res:
            transformed_data.append(res)
            stats_trans["valid"] += 1
        else:
            stats_trans["invalid"] += 1
            
    print(f"Transformación CAT: Total {stats_trans['total']}, Válidos {stats_trans['valid']}, Inválidos {stats_trans['invalid']}")
    return transformed_data


if __name__ == "__main__":
    # Recupera datos de la API  
    data_list = get_api_data("cat")
    
    # Transforma datos
    transformed_data = transform_cat_data(data_list)

    # Guarda datos transformados a json (solo debug)
    save_transformed_to_json(transformed_data, "cat")

    # Sube datos a la BD (Independiente de lo anterior)
    transformed_data_to_database(transformed_data, "cat")
