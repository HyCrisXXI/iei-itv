# src/extractors/extractor_cat.py
import re
import sys
import xml.etree.ElementTree as ET

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.common.dependencies import get_api_data, save_transformed_to_json, transformed_data_to_database
from src.common.errors import error_msg, register_rejection, register_repair
from src.common.validators import clean_invalid_email

provinciaCat = ["Tarragona", "Lleida", "Girona", "Barcelona"]

cpCat = ["43", "25", "17", "08"]

SOURCE_TAG = "cat"

mappingProvincia = {
    "08": "Barcelona",
    "17": "Girona",
    "25": "Lleida",
    "43": "Tarragona",
}

PROVINCIA_TO_CODE = {name.lower(): code for code, name in mappingProvincia.items()}

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
    localidad_nombre = transformed.get("l_nombre")
    nom_prov = transformed.get("p_nombre")
    nom_prov_clean = nom_prov.strip() if isinstance(nom_prov, str) else None

    def _register_fix(motivo: str, operacion: str) -> None:
        register_repair(SOURCE_TAG, est_name, localidad_nombre, motivo, operacion)

    def _register_reject(motivo: str) -> None:
        register_rejection(SOURCE_TAG, est_name, localidad_nombre, motivo)
    
    # 1. Validar Código Postal en Cataluña
    if p_code not in cpCat:
        inferred_code = None
        if nom_prov_clean:
            inferred_code = PROVINCIA_TO_CODE.get(nom_prov_clean.lower())

        if inferred_code:
            transformed["p_cod"] = inferred_code
            p_code = inferred_code
            _register_fix(
                "Código postal ausente o inválido",
                f"Código ajustado a {inferred_code} usando provincia {nom_prov_clean}",
            )
        else:
            motivo = f"Código postal ({p_code}) fuera de rango CAT"
            error_msg(est_name or "Desconocida", [motivo])
            _register_reject(motivo)
            return None 

    # 2. Comprobar coincidencia entre Provincia y Código Postal
    if mappingProvincia.get(p_code) != nom_prov:
        if p_code in cpCat:
            transformed["p_nombre"] = mappingProvincia[p_code]
            _register_fix(
                "La provincia no coincidía con el código postal",
                f"Provincia ajustada a {mappingProvincia[p_code]}",
            )
        else:
            motivo = f"Provincia ({nom_prov}) no coincide con código postal ({p_code})"
            error_msg(est_name or "Desconocida", [motivo])
            _register_reject(motivo)
            return None

    # 3. Validar Nombre Provincia
    prov_name = transformed.get("p_nombre")
    if prov_name not in provinciaCat:
        if p_code in cpCat:
            prov_name = mappingProvincia[p_code]
            transformed["p_nombre"] = prov_name
            _register_fix(
                "Provincia no válida",
                f"Provincia reasignada a {prov_name}",
            )
        else:
            error_msg(est_name or "Desconocida", ["p_nombre"])
            _register_reject("Provincia no reconocida")
            return None
            
    if not prov_name:
        motivo = "Provincia no identificada"
        error_msg(est_name or "Desconocida", [motivo])
        _register_reject(motivo)
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
    seen_records: dict[str, dict] = {}
    deduped_records: list[dict] = []

    def _normalize_name(value: str | None) -> str:
        return str(value).strip().lower() if value else ""

    def _has_postal(record: dict) -> bool:
        cp_value = _extract_value(record.get("cp"))
        if cp_value is None:
            return False
        return bool(str(cp_value).strip())

    def _richness_score(record: dict) -> int:
        fields = [
            "adre_a",
            "horari_de_servei",
            "correu_electr_nic",
            "web",
            "lat",
            "long",
        ]
        return sum(1 for field in fields if str(_extract_value(record.get(field)) or "").strip())

    for record in data_list:
        stats_trans["total"] += 1
        raw_name = record.get("denominaci")
        key = _normalize_name(raw_name)
        if not key:
            deduped_records.append(record)
            continue

        if key not in seen_records:
            index = len(deduped_records)
            deduped_records.append(record)
            seen_records[key] = {"index": index, "record": record}
            continue

        stats_trans["invalid"] += 1
        existing_meta = seen_records[key]
        existing_record = existing_meta["record"]
        existing_has_cp = _has_postal(existing_record)
        incoming_has_cp = _has_postal(record)
        replace = False
        repair_action = "Omitido por duplicado en origen"

        if incoming_has_cp and not existing_has_cp:
            replace = True
            repair_action = "Se mantuvo la versión con código postal válido"
        elif incoming_has_cp == existing_has_cp:
            if _richness_score(record) > _richness_score(existing_record):
                replace = True
                repair_action = "Se mantuvo la versión con más información"

        register_repair(
            SOURCE_TAG,
            raw_name,
            record.get("municipi"),
            "Registro duplicado detectado",
            repair_action,
        )

        if replace:
            idx = existing_meta["index"]
            deduped_records[idx] = record
            existing_meta["record"] = record

    for record in deduped_records:
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
