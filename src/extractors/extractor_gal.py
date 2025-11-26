# src/extractors/extractor_gal.py
import sys
import re
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
# from wrappers.wrapper_gal import csvtojson
from database.models import TipoEstacion, Provincia, Localidad, Estacion
from database.session import get_db

import csv # Temporal

DD_REGEX = re.compile(r"^[+-]?\d+(\.\d+)?$")

# Función temporal para la primera entrega
def csvtojson() -> list:
    csv_path = (
        Path(__file__).resolve()
        .parent.parent.parent / "data" / "Estacions_ITV.csv"
    )
    if not csv_path.exists():
        raise FileNotFoundError(f"Estacions_ITV.csv not found at: {csv_path}")

    with csv_path.open("r", encoding="ISO-8859-1") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        data = [row for row in reader]
    return data

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
def error_msg(e_nombre: str, missing_fields):
    print(f"Estación '{e_nombre}' no tiene datos en: {', '.join(missing_fields)}")

def transform_json(record: dict) -> dict:
    KEY_MAPPING = {
        "NOME DA ESTACIÓN": "e_nombre",
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
    e_nombre = transformed.get("e_nombre", None)
    
    # Elimina clave original
    coord_string = transformed.pop("coordenadas", None)
    if coord_string:
        parts = [p.strip() for p in coord_string.split(',', 1)]
        
        if len(parts) == 2:
            lat = ddm_to_dd_or_pass(parts[0]) # Función de conversión DDM/DD
            lon = ddm_to_dd_or_pass(parts[1])
            
            transformed["latitud"] = lat # Clave nueva con datos transformados
            transformed["longitud"] = lon
        else:
            error_msg(e_nombre, ["coordenadas"])
            transformed["latitud"] = None
            transformed["longitud"] = None

    cod_postal = str(transformed.get("codigo_postal", None))
    if cod_postal:
        transformed["p_cod"] = cod_postal[:2]
    else:
        error_msg(e_nombre, ["codigo_postal"])
        transformed["p_cod"] = None
    return transformed

def transformed_data_to_database():
    data_list = csvtojson()
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
            data = transform_json(record)
            # Se obtiene aquí para evitar repetir código y de fallback desconocida pq es necesario para mensajes de error
            e_nombre = data.get("e_nombre", "Desconocida")

            # Provincia
            prov_name = data.get("p_nombre")
            prov_cod = data.get("p_cod")
            prov = None

            if prov_cod:
                prov = session.query(Provincia).filter_by(codigo=prov_cod).first()
                if prov:
                    # Si el nombre es distinto, actualiza el nombre
                    if prov.nombre != prov_name:
                        prov.nombre = prov_name
                        session.flush()
            else:
                prov = session.query(Provincia).filter_by(nombre=prov_name).first()

            if not prov:
                prov_args = {"nombre": prov_name}
                if prov_cod:
                    prov_args["codigo"] = prov_cod
                prov = Provincia(**prov_args)
                session.add(prov)
                session.flush()
            # Esto añade a la caché la provincia si ya está en la BD, para no volverla a subir
            prov_cache[prov_name] = prov

            # Localidad
            loc_key = (data.get("l_nombre"), prov.codigo)
            loc = loc_cache.get(loc_key)
            if loc is None:
                loc = session.query(Localidad).filter_by(nombre=data.get("l_nombre"), codigo_provincia=prov.codigo).first()
                if loc is None:
                    loc = Localidad(nombre=data.get("l_nombre"), codigo_provincia=prov.codigo)
                    session.add(loc)
                    session.flush()
                loc_cache[loc_key] = loc

            # Estacion
            est_key = (e_nombre, loc.codigo)
            if est_key in est_cache:
                continue
            est = session.query(Estacion).filter_by(nombre=e_nombre, codigo_localidad=loc.codigo).first()
            if est:
                est_cache[est_key] = est
                continue
            
            codigo_postal = data.get("codigo_postal")
            if len(codigo_postal) != 5:
                error_msg(e_nombre, ["codigo_postal"])
                continue

            contacto = data.get("contacto", "")
            if not contacto:
                error_msg(e_nombre, ["contacto"])
                
            # Solo sube los campos que tengan datos
            required_fields = [
                "direccion", "codigo_postal", "latitud", "longitud", "horario", "contacto", "url"
            ]
            valid_fields, missing_fields = filter_valid_fields(data, required_fields)
            if missing_fields:
                error_msg(e_nombre, missing_fields)

            estacion = Estacion(
                nombre=e_nombre,
                tipo=TipoEstacion.Estacion_fija,
                codigo_localidad=loc.codigo,
                origen_datos="gal",
                **valid_fields
            )
            session.add(estacion)
            est_cache[est_key] = estacion
            
        session.commit()

if __name__ == "__main__":
    # Normaliza datos a json (solo debug)
    data_list = csvtojson()
    transformed_data = [transform_json(record) for record in data_list]
    out_path = Path(__file__).resolve().parent / "gal.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(transformed_data, jsonfile, indent=4, ensure_ascii=False)
    
    # Sube datos a la BD (Independiente de lo anterior)
    transformed_data_to_database()