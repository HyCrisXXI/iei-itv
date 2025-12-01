# src/extractors/extractor_cv.py
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from geopy.geocoders import Nominatim
import time
import re
from database.models import TipoEstacion, Provincia, Localidad, Estacion
from database.session import get_db, create_db_and_tables
import unicodedata
from difflib import get_close_matches
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from extractors.selenium_cv import geolocate_google_selenium


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



#Normaliza provincias automáticamente corrigiendo errores
PROVINCIAS_VALIDAS = ["valencia","alicante","castellon"]

def normalizar_provincia(nombre: str | None) -> str | None:
    if not nombre:
        return None
    
    txt = unicodedata.normalize("NFD", nombre)
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn").lower().strip()

    if txt in PROVINCIAS_VALIDAS:
        return txt.capitalize()

    match = get_close_matches(txt, PROVINCIAS_VALIDAS, n=1, cutoff=0.75)
    if match:
        return match[0].capitalize()

    return None



#Construye el nombre final de la estación basado en municipio o provincia
def build_station_name(municipio: str | None) -> str | None:
    if not municipio or not municipio.strip():
        return None
    return f"ITV {municipio.strip()} SITVAL"




#Limpia el texto del tipo de estación
def normalize_station_type(tipo: str | None) -> str:
    if not tipo:
        return "Otros"
    cleaned = tipo.replace("Estación", "").strip()
    return cleaned if cleaned else "Otros"



#Extrae dominio de un email
def extract_domain_from_email(email: str) -> str | None:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1]



#Muestra advertencia si un registro tiene campos faltantes
def error_msg(e_nombre: str, missing_fields):
    print(f"Estación '{e_nombre}' incompleta → {', '.join(missing_fields)}")



#Transforma los datos de cada estación del json
def transform_cv_record(record: dict, driver=None) -> dict | None:
    tipo_raw = record.get("TIPO ESTACIÓN", "")
    tipo_estacion = normalize_station_type(tipo_raw)
    
    correo = record.get("CORREO")
    url = extract_domain_from_email(correo)
    horario = record.get("HORARIOS")
    contacto = record.get("CORREO")
    
    # Campos comunes para fijas y no fijas
    transformed = {
        "tipo_estacion": tipo_estacion,
        "horario": horario,
        "contacto": contacto,
        "url": url
    }
    # Estos dos se usarán de distinta forma tanto en estaciones fijas como no fijas
    direccion = record.get("DIRECCIÓN")
    provincia = normalizar_provincia(record.get("PROVINCIA"))
    
    # Estaciones fijas: requieren todos los datos (salvo descripción)
    if "fija" in tipo_estacion.lower():
        municipio = record.get("MUNICIPIO")
        codigo_postal = record.get("C.POSTAL")
        cod_postal_string = str(codigo_postal) if codigo_postal else None
        p_cod = cod_postal_string[:2] if cod_postal_string else None

        if not cod_postal_string:
            print(f"Estación fija sin código postal, se descarta → {municipio} / {direccion}")
            return None

        lat, lon = geolocate_google_selenium(driver, direccion, municipio)
        # Aquí solo comprueba lat, ya que el metodo geolocate, o devuelve los dos, o ninguno
        if not lat:
            print(f"No tiene localización → {municipio} / {direccion}")
            return None

        nombre = build_station_name(municipio)
        transformed.update({
            "nombre": nombre,
            "direccion": direccion,
            "codigo_postal": codigo_postal,
            "p_cod": p_cod,
            "l_nombre": municipio,
            "p_nombre": provincia,
            "lat": lat,
            "lon": lon
        })
    else:
        # No fijas: solo requieren dirección como nombre, tipo, horario, contacto, url y... direccion?
        transformed.update({
            "nombre": direccion,
            # Aquí dudo si poner la provincia como dirección, ya q no se puede poner 
            # directamente en la tabla provincia, al faltar la tabla intermedia localidad
            # en estaciones que no son fijas
            "direccion": provincia
        })

    return transformed


def _map_tipo_enum(tipo_str: str) -> TipoEstacion:
    if not tipo_str:
        return TipoEstacion.Otros
    t = tipo_str.strip().lower()
    if 'fija' in t:
        return TipoEstacion.Estacion_fija
    if 'mov' in t or 'móvil' in t:
        return TipoEstacion.Estacion_movil
    return TipoEstacion.Otros


#Inserta los registros ya transformados en la base de datos
#evitando duplicados y creando provincia/localidad si no existen
def insert_transformed_to_db(transformed_list: list) -> tuple[list, list]:
    inserted = []
    skipped = []

    with next(get_db()) as session:
        prov_cache = {}
        loc_cache = {}
        est_cache = {}

        for rec in transformed_list:
            nombre = rec.get('nombre')
            tipo = rec.get('tipo_estacion', '').lower()
            motivo_skip = None

            # Para fijas, requiere provincia y localidad
            if "fija" in tipo:
                p_nombre = normalizar_provincia(rec.get('p_nombre'))
                l_nombre = rec.get('l_nombre')
                p_cod = rec.get('p_cod')

                # Si no hay provincia o localidad, se descarta
                if not p_nombre:
                    motivo_skip = "Estación sin provincia, no insertada"
                elif not l_nombre:
                    motivo_skip = "Estación sin localidad, no insertada"

                if motivo_skip:
                    skipped.append((nombre, motivo_skip))
                    continue

                # ---- PROVINCIA ----
                prov = prov_cache.get(p_nombre)
                if prov is None:
                    prov = session.query(Provincia).filter_by(nombre=p_nombre).first()
                    if not prov:
                        prov = Provincia(
                            nombre=p_nombre,
                            codigo=int(p_cod) if p_cod else None
                        )
                        session.add(prov)
                        session.flush()
                    prov_cache[p_nombre] = prov

                # ---- LOCALIDAD ----
                loc_key = (l_nombre, prov.codigo)
                loc = loc_cache.get(loc_key)
                if loc is None:
                    loc = session.query(Localidad).filter_by(
                        nombre=l_nombre, codigo_provincia=prov.codigo
                    ).first()
                    if loc is None:
                        loc = Localidad(nombre=l_nombre, codigo_provincia=prov.codigo)
                        session.add(loc)
                        session.flush()
                    loc_cache[loc_key] = loc
            else:
                prov = None
                loc = None

            # ---- ESTACIÓN ----
            if not nombre:
                skipped.append((nombre, "Estación sin nombre, no insertada"))
                continue

            codigo_localidad = loc.codigo if loc else None

            est_key = (nombre, codigo_localidad)
            if est_key in est_cache or (codigo_localidad and session.query(Estacion).filter_by(
                nombre=nombre, codigo_localidad=codigo_localidad
            ).first()):
                skipped.append((nombre, "Estación duplicada, no insertada"))
                continue

            estacion = Estacion(
                nombre=nombre,
                tipo=_map_tipo_enum(rec.get('tipo_estacion')),
                codigo_localidad=codigo_localidad,
                origen_datos='cv',
                direccion=rec.get('direccion'),
                codigo_postal=int(rec.get('codigo_postal')) if rec.get('codigo_postal') else None,
                latitud=rec.get('lat'),
                longitud=rec.get('lon'),
                horario=rec.get('horario'),
                contacto=rec.get('contacto'),
                url=rec.get('url'),
            )
            session.add(estacion)
            est_cache[est_key] = estacion
            inserted.append(nombre)

        session.commit()

    return inserted, skipped

def save_transformed_to_json(transformed_list: list, out_path: Path = None):
    if out_path is None:
        out_path = Path(__file__).resolve().parent / "cv.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(transformed_list, jsonfile, indent=4, ensure_ascii=False)

def process_and_transform_data(data_list: list, driver) -> list:
    transformed_list = []
    for item in data_list:
        # municipio = item.get("MUNICIPIO", "")
        # direccion = item.get("DIRECCIÓN", "")
        # print(f"Procesando: {direccion}, {municipio}...")

        rec = transform_cv_record(item, driver=driver)
        if not rec:
            # print(f"Registro descartado (provincia inválida o no geolocaliza si es fija) → {municipio}")
            continue

        transformed_list.append(rec)
        print(f"Guardado {rec['nombre']}")
    return transformed_list

if __name__ == "__main__":
    data_list = jsontojson()

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=options)

    try:
        transformed_list = process_and_transform_data(data_list, driver)
    finally:
        driver.quit()

    # Guardar el JSON ya transformado
    save_transformed_to_json(transformed_list)
    
    print(f"Transformación: {len(data_list)} registros originales, {len(transformed_list)} transformados, {len(data_list) - len(transformed_list)} descartados en transformación.")

    # Automáticamente insertar en la base de datos
    try:
        inserted, skipped = insert_transformed_to_db(transformed_list)
        print(f"Insercción en BD completa. Insertados: {len(inserted)}, Saltados: {len(skipped)}")
        if skipped:
            print("Registros descartados en BD y motivo:")
            for nombre, motivo in skipped:
                print(f"  - {nombre}: {motivo}")
    except Exception as e:
        print(f"Error insertando datos en BD: {e}")