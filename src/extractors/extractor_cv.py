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
from common.db_storage import save_stations
from common.errors import error_msg


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
        "tipo": tipo_estacion,
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
            error_msg(municipio or "Desconocida", ["codigo_postal"])
            return None
            
        nombre = build_station_name(municipio)

        # Validación de campos obligatorios para estaciones fijas
        if not provincia:
            error_msg(nombre, ["provincia"])
            return None
        if not municipio:
            error_msg(nombre, ["municipio"])
            return None

        # Geolocalización mediante Selenium
        lat, lon = geolocate_google_selenium(driver, direccion, municipio)
        # Solo comprobamos latitud, ya que el método devuelve ambas o ninguna
        if not lat:
            error_msg(nombre, ["latitud/longitud"])
            return None

        transformed.update({
            "nombre": nombre,
            "direccion": direccion,
            "codigo_postal": codigo_postal,
            "p_cod": p_cod,
            "l_nombre": municipio,
            "p_nombre": provincia,
            "latitud": lat,
            "longitud": lon
        })
    else:
        # Estaciones no fijas (móviles o de otro tipo)
        transformed.update({
            "nombre": direccion,
            "direccion": provincia, 
            "latitud": None,
            "longitud": None,
            "p_nombre": None,
            "l_nombre": None,
            "p_cod": None
        })
        
    # Comprobar si falta el nombre tras la transformación
    missing = []
    if not transformed.get("nombre"): missing.append("nombre")
    
    return transformed

def process_and_transform_data(data_list: list, driver) -> list:
    transformed_list = []
    for item in data_list:

        rec = transform_cv_record(item, driver=driver)
        if not rec:
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
    save_transformed_to_json(transformed_list, "cv")
    
    print(f"Transformación: {len(data_list)} registros originales, {len(transformed_list)} transformados, {len(data_list) - len(transformed_list)} descartados en transformación.")

    # Automáticamente insertar en la base de datos
    try:
        stats = save_stations(transformed_list, "cv")
        print(f"Insercción en BD completa. Insertados: {stats['inserted']}, Saltados: {stats['skipped']}")
    except Exception as e:
        print(f"Error insertando datos en BD: {e}")