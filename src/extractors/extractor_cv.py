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
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
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



def transform_cv_record(record: dict, station_names_map=None) -> dict | None:
    tipo_raw = record.get("TIPO ESTACIÓN", "")
    KEY_MAPPING = {
        "TIPO ESTACIÓN": "tipo_estacion",
        "DIRECCIÓN":     "direccion",
        "C.POSTAL":      "codigo_postal",
        "HORARIOS":      "horario",
        "CORREO":        "contacto",
        "MUNICIPIO":     "l_nombre",
        "PROVINCIA":     "p_nombre"
    }

    transformed = {}
    for old_key, new_key in KEY_MAPPING.items():
        if old_key in record:
            transformed[new_key] = record[old_key]


    transformed["tipo_estacion"] = normalize_station_type(transformed.get("tipo_estacion") or tipo_raw)


    cod_postal_string = str(transformed.get("codigo_postal", ""))
    transformed["p_cod"] = cod_postal_string[:2] if cod_postal_string else None


    correo = transformed.get("contacto")
    transformed["url"] = extract_domain_from_email(correo)


    provincia = normalizar_provincia(transformed.get("p_nombre"))
    if provincia is None:
        return None

    # Geolocalización con Selenium + Google Maps
    direccion = transformed.get("direccion")
    municipio = transformed.get("l_nombre")

    lat, lon = geolocate_google_selenium(driver, direccion, municipio)

    if not lat or not lon:
        print(f"No geolocaliza → {municipio} / {direccion}")
        return None

    transformed["lat"] = lat
    transformed["lon"] = lon


    transformed["nombre"] = build_station_name(municipio)


    required_fields = ["direccion", "codigo_postal", "lat", "lon", "horario", "contacto", "url"]


    missing = [f for f in required_fields if not transformed.get(f)]
    if missing:
        error_msg(transformed["nombre"], missing)

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
def insert_transformed_to_db(transformed_list: list) -> tuple[int, int]:
    create_db_and_tables()
    inserted = 0
    skipped = 0

    with next(get_db()) as session:
        prov_cache = {}
        loc_cache = {}
        est_cache = {}

        for rec in transformed_list:
            #transform_cv_record
            raw_p_nombre = rec.get('p_nombre')
            p_nombre = normalizar_provincia(raw_p_nombre)
            l_nombre = rec.get('l_nombre')
            p_cod = rec.get('p_cod')
            nombre = rec.get('nombre')

            #Sin provincia no se crea nada
            if not p_nombre:
                print(f"Registro sin provincia válida, se descarta → {rec.get('direccion')}")
                skipped += 1
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

            #Sin municipio no hay localidad ni estación
            if not l_nombre:
                skipped += 1
                continue

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

            # ---- ESTACIÓN ----
            # Si no viene nombre, se genera con el municipio
            if not nombre:
                nombre = build_station_name(l_nombre)
            if not nombre:
                print(f"Estación sin nombre (municipio vacío), se descarta")
                skipped += 1
                continue

            est_key = (nombre, loc.codigo)
            if est_key in est_cache or session.query(Estacion).filter_by(
                nombre=nombre, codigo_localidad=loc.codigo
            ).first():
                print(f"Estación duplicada, no insertada → {nombre}")
                skipped += 1
                continue

            estacion = Estacion(
                nombre=nombre,
                tipo=_map_tipo_enum(rec.get('tipo_estacion')),
                codigo_localidad=loc.codigo,
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
            inserted += 1

        session.commit()

    return inserted, skipped

if __name__ == "__main__":

    data_list = jsontojson()

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    driver = webdriver.Chrome(options=options)

    transformed_list = []

    try:
        for item in data_list:
            tipo = item.get("TIPO ESTACIÓN", "")
            if "Móvil" in tipo or "Agrícola" in tipo:
                continue

            municipio = item.get("MUNICIPIO", "")
            direccion = item.get("DIRECCIÓN", "")

            print(f"Procesando: {direccion}, {municipio}...")

            rec = transform_cv_record(item)

            if rec is None:
                print(f"Registro descartado (provincia inválida o no geolocaliza) → {municipio}")
                continue


            transformed_list.append(rec)
            print(f"Guardado {rec['nombre']} ({rec['lat']}, {rec['lon']})")

    finally:
        driver.quit()

    # Guardar el JSON ya transformado
    out_path = Path(__file__).resolve().parent / "cv.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(transformed_list, jsonfile, indent=4, ensure_ascii=False)

    # Automáticamente insertar en la base de datos
    try:
        inserted, skipped = insert_transformed_to_db(transformed_list)
        print(f"DB insertion completed. Inserted: {inserted}, Skipped: {skipped}")
    except Exception as e:
        print(f"Error inserting data into DB: {e}")