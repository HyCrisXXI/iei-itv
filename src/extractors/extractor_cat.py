# src/extractors/extractor_cat.py
import sys
import xml.etree.ElementTree as ET
import json
import re
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.models import TipoEstacion, Provincia, Localidad, Estacion
from database.session import get_db
from common.db_storage import save_stations
from common.errors import error_msg

provinciaCat = ["Tarragona", "Lleida", "Girona", "Barcelona"]

cpCat = ["43", "25", "17", "08"]

mappingProvincia = {
    "08": "Barcelona",
    "17": "Girona",
    "25": "Lleida",
    "43": "Tarragona",
}


def xmltojson() -> list:
    xml_path = (
        Path(__file__).resolve()
        .parent.parent.parent / "data" / "ITV-CAT.xml"
    )

    if not xml_path.exists():
        raise FileNotFoundError(f"ITV-CAT.xml not found at: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    if (
        len(root) == 1
        and root[0].tag == "row"
        and all(child.tag == "row" for child in root[0])
    ):
        rows = root[0].findall("row")
    else:
        rows = root.findall("row")

    data = []
    for row in rows:
        record = {}
        # añade elementos tipo (_id, _uuid, etc.)
        record.update(row.attrib)

        for child in row:
            if list(child.attrib.keys()) == ["url"] and (not child.text or not child.text.strip()):
                record[child.tag] = child.attrib["url"]
            elif child.attrib:
                entry = dict(child.attrib)
                if child.text and child.text.strip():
                    entry["text"] = child.text.strip()
                record[child.tag] = entry
            else:
                record[child.tag] = child.text.strip() if child.text else None
        if record:
            data.append(record)

    return data
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


def _safe_int(value) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None

def transform_cat_record(record: dict) -> dict:
    KEY_MAPPING = {
        "denominaci": "nombre",
        "adre_a": "direccion",
        "cp": "codigo_postal",
        "long": "longitud",
        "lat": "latitud",
        "horari_de_servei": "horario",
        "correu_electr_nic": "contacto",
        "web": "url",
        "codi_municipi": "codigo_localidad",
        "municipi": "nombre_localidad",
        "serveis_territorials": "nombre_provincia",
    }
    
    transformed = {} # Claves estandarizadas
    for old_key, new_key in KEY_MAPPING.items():
        value = _extract_value(record.get(old_key))
        if value is not None:
            transformed[new_key] = value

    transformed["tipo"] = "fija"

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
        return None 

    # 2. Comprobar coincidencia entre Provincia y Código Postal
    nom_prov = transformed.get("nombre_provincia")
    
    if mappingProvincia.get(p_code) != nom_prov:
        if p_code in cpCat:
            transformed["nombre_provincia"] = mappingProvincia[p_code]
        else:
            return None

    # 3. Validar Nombre Provincia
    prov_name = transformed.get("nombre_provincia")
    if prov_name not in provinciaCat:
        if p_code in cpCat:
            prov_name = mappingProvincia[p_code]
            transformed["nombre_provincia"] = prov_name
        else:
            error_msg(est_name or "Desconocida", ["nombre_provincia"])
            return None
            
    if not prov_name:
        return None

    # Ajuste final de claves para la función de guardado común
    transformed["nombre"] = "ITV " + (est_name or "")
    transformed["p_nombre"] = transformed["nombre_provincia"]
    transformed["l_nombre"] = transformed["nombre_localidad"]
    
    # Validar campos requeridos

    required_fields = [
        "direccion", "codigo_postal", "latitud", "longitud", "horario", "contacto", "url"
    ]
    missing = [f for f in required_fields if not transformed.get(f)]
    if missing:
        error_msg(transformed["nombre"], missing)
        
    return transformed


def transformed_data_to_database(records: list | None = None):
    data_list = records if records is not None else xmltojson()
    
    ready_data = []
    for rec in data_list:
        # Detectar si es registro crudo o ya transformado
        if "p_nombre" in rec:
            data = rec
        else:
            data = transform_cat_record(rec)
            
        if data:
            ready_data.append(data)

    stats = save_stations(ready_data, "cat")
    print(f"Inserción completa. Insertados: {stats['inserted']}, Omitidos: {stats['skipped']}, Errores: {len(stats['errors'])}")

if __name__ == "__main__":
    data_list = xmltojson()
    transformed_data = [transform_cat_record(record) for record in data_list]
    out_path = Path(__file__).resolve().parent / "cat.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(transformed_data, jsonfile, indent=4, ensure_ascii=False) # minify: indent=None, separators=(",", ":")

    transformed_data_to_database(data_list)
