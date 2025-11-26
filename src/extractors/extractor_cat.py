# src/extractors/extractor_cat.py
import sys
import xml.etree.ElementTree as ET
import json
import re
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.models import TipoEstacion, Provincia, Localidad, Estacion
from database.session import get_db

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

def provincia_normalizada(nombre, codigo_postal):
    """Normaliza nombres de provincia y prioriza la que tiene código postal."""
    nombre = (nombre or "").strip().lower()
    if nombre in ["valencia", "valència"]:
        return "Valencia" if codigo_postal else "València"
    if nombre in ["alicante", "aligante"]:
        return "Alicante" if codigo_postal else "Aligante"
    return nombre.title()

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

    scaled = number / 1_000_000
    if -limit <= scaled <= limit:
        return round(scaled, 6)

    scaled = number / 100_000
    if -limit <= scaled <= limit:
        return round(scaled, 6)
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

    locator = record.get("localitzador_a_google_maps")
    if (lat is None or lon is None) and isinstance(locator, dict):
        url = locator.get("url")
        if isinstance(url, str):
            match = re.search(r"q=([+-]?\d+(?:\.\d+)?)\+([+-]?\d+(?:\.\d+)?)", url)
            if match:
                lat_candidate = _normalize_coordinate(match.group(1), is_latitude=True)
                lon_candidate = _normalize_coordinate(match.group(2), is_latitude=False)
                if lat is None:
                    lat = lat_candidate
                if lon is None:
                    lon = lon_candidate

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

    # Cache para provincias normalizadas
    prov_cache = {}
    prov_seen = {}

    with next(get_db()) as session:
        loc_cache = {}
        est_cache = {}

        for record in data_list:
            data = transform_itv_record(record)
            est_name = data.get("nombre", "Desconocida")
            prov_name_raw = data.get("nombre_provincia")
            codigo_postal = data.get("codigo_postal")
            prov_name = provincia_normalizada(prov_name_raw, codigo_postal)
            data["nombre_provincia"] = prov_name

            # Prioriza provincia con código postal, muestra error si hay duplicidad
            prov_key = prov_name.lower()
            prov_code_int = _safe_int(data.get("p_cod"))
            if prov_key in prov_seen:
                # Si ya existe, solo actualiza si el nuevo tiene código postal y el anterior no
                prev = prov_seen[prov_key]
                if not prev["codigo_postal"] and codigo_postal:
                    prov_seen[prov_key] = {"nombre": prov_name, "codigo_postal": codigo_postal, "codigo": prov_code_int}
                else:
                    error_msg(est_name, [f"Duplicidad provincia '{prov_name_raw}' tratada como '{prov_name}'"])
            else:
                prov_seen[prov_key] = {"nombre": prov_name, "codigo_postal": codigo_postal, "codigo": prov_code_int}

        # Inserta provincias únicas
        for prov_key, prov_info in prov_seen.items():
            prov = None
            # Buscar primero por código si existe
            if prov_info["codigo"]:
                prov = session.query(Provincia).filter_by(codigo=prov_info["codigo"]).first()
                if prov:
                    # Si el nombre es distinto, muestra advertencia
                    if prov.nombre != prov_info["nombre"]:
                        print(f"Advertencia: provincia con código {prov_info['codigo']} ya existe como '{prov.nombre}', no se inserta '{prov_info['nombre']}'")
                # Si existe, no insertar, solo añadir a la caché
            if not prov:
                # Si no existe por código, buscar por nombre
                prov = session.query(Provincia).filter_by(nombre=prov_info["nombre"]).first()
            if not prov:
                prov_args = {"nombre": prov_info["nombre"]}
                if prov_info["codigo"]:
                    prov_args["codigo"] = prov_info["codigo"]
                prov = Provincia(**prov_args)
                session.add(prov)
                session.flush()
            prov_cache[prov_info["nombre"]] = prov

        # Inserta localidades y estaciones
        for record in data_list:
            data = transform_itv_record(record)
            est_name = data.get("nombre", "Desconocida")
            prov_name_raw = data.get("nombre_provincia")
            codigo_postal = data.get("codigo_postal")
            prov_name = provincia_normalizada(prov_name_raw, codigo_postal)
            data["nombre_provincia"] = prov_name

            prov = prov_cache.get(prov_name)
            if not prov:
                error_msg(est_name, [f"Provincia '{prov_name}' no encontrada"])
                continue

            loc_name = data.get("nombre_localidad")
            if not loc_name:
                error_msg(est_name, ["nombre_localidad"])
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

            est_key = (est_name, loc.codigo)
            if est_key in est_cache:
                continue
            est = session.query(Estacion).filter_by(nombre=est_name, codigo_localidad=loc.codigo).first()
            if est:
                est_cache[est_key] = est
                continue

            codigo_postal_int = _safe_int(data.get("codigo_postal"))
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
