# src/extractors/extractor_cat.py
import sys
import xml.etree.ElementTree as ET
import json
import re
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.models import TipoEstacion, Provincia, Localidad, Estacion
from database.session import get_db

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

def error_msg(e_nombre: str, missing_fields):
    print(f"Estación '{e_nombre}' no tiene datos en: {', '.join(missing_fields)}")

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

def transform_itv_record(record: dict) -> dict:
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
    return transformed


def transformed_data_to_database(records: list | None = None):
    data_list = records if records is not None else xmltojson()
    def filter_valid_fields(data: dict, required_fields: list) -> dict:
        valid = {}
        missing = []
        for field in required_fields:
            value = data.get(field)
            if value is not None and value != "":
                valid[field] = value
            else:
                missing.append(field)
        return valid, missing
    with next(get_db()) as session:
        prov_cache = {}
        loc_cache = {}
        est_cache = {}

        for record in data_list:
            data = transform_itv_record(record)

            p_code = data.get("p_cod")
            if p_code not in cpCat:
                print(f"Omitiendo estación '{data.get('nombre', 'Desconocida')}' con código postal fuera de Cataluña: '{data.get('codigo_postal', 'Desconocido')}'")
                continue

            if mappingProvincia[p_code] != data.get("nombre_provincia"):
                print(f"Advertencia: estación '{data.get('nombre', 'Desconocida')}' tiene provincia '{data.get('nombre_provincia', 'Desconocida')}' que no coincide con código postal '{data.get('codigo_postal', 'Desconocido')}' se ajustará el nombre de la provincia si es posible.")
                if p_code in cpCat:
                    data["nombre_provincia"] = mappingProvincia[p_code]
                    print(f"Ajustando provincia de estación '{data.get('nombre', 'Desconocida')}' a '{data['nombre_provincia']}' según código postal.")
                else:
                    print(f"Omitiendo estación '{data.get('nombre', 'Desconocida')}' por inconsistencia en provincia y código postal.")
                    continue

            prov_name = data.get("nombre_provincia")
            if prov_name not in provinciaCat:
                if p_code in cpCat:
                    prov_name = mappingProvincia[p_code]
                    print(f"Ajustando provincia de estación '{data.get('nombre', 'Desconocida')}' de '{data.get('nombre_provincia', 'Desconocida')}' a '{prov_name}' según código postal.")
                else:
                    error_msg(data.get("nombre", "Desconocida"), ["nombre_provincia"])
                    continue
            if not prov_name:
                continue
            prov = prov_cache.get(prov_name)
            prov_code_int = _safe_int(data.get("p_cod"))
            if not prov:
                query = session.query(Provincia)
                if prov_code_int is not None:
                    prov = query.filter_by(codigo=prov_code_int).first()
                if not prov:
                    prov = query.filter_by(nombre=prov_name).first()
                if not prov:
                    if prov_code_int is None:
                        continue
                    prov = Provincia(codigo=prov_code_int, nombre=prov_name)
                    session.add(prov)
                    session.flush()
                prov_cache[prov_name] = prov

            loc_name = data.get("nombre_localidad")
            if not loc_name:
                continue
            loc_key = (loc_name, prov.codigo)
            loc = loc_cache.get(loc_key)
            if loc is None:
                loc = session.query(Localidad).filter_by(nombre=loc_name, codigo_provincia=prov.codigo).first()
                if loc is None:
                    loc = Localidad(nombre=loc_name, codigo_provincia=prov.codigo)
                    session.add(loc)
                    session.flush()
                loc_cache[loc_key] = loc

            est_name = "ITV " + data.get("nombre")
            if not est_name:
                continue
            est_key = (est_name, loc.codigo)
            if est_key in est_cache:
                continue
            est = session.query(Estacion).filter_by(nombre=est_name, codigo_localidad=loc.codigo).first()
            if est:
                est_cache[est_key] = est
                continue

            # Solo sube los campos que tengan datos
            required_fields = [
                "direccion", "codigo_postal", "latitud", "longitud", "horario", "contacto", "url"
            ]
            valid_fields, missing_fields = filter_valid_fields(data, required_fields)
            if missing_fields:
                error_msg(est_name, missing_fields)

            estacion = Estacion(
                nombre=est_name,
                tipo=TipoEstacion.Estacion_fija,
                codigo_localidad=loc.codigo,
                origen_datos="cat",
                **valid_fields
            )
            session.add(estacion)
            est_cache[est_key] = estacion

        session.commit()

if __name__ == "__main__":
    data_list = xmltojson()
    transformed_data = [transform_itv_record(record) for record in data_list]
    out_path = Path(__file__).resolve().parent / "cat.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(transformed_data, jsonfile, indent=4, ensure_ascii=False) # minify: indent=None, separators=(",", ":")

    transformed_data_to_database(data_list)
