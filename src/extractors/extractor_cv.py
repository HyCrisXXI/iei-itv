# src/extractors/extractor_cv.py
import unicodedata
import sys
from difflib import get_close_matches
from selenium import webdriver
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from extractors.selenium_cv import geolocate_google_selenium
from common.dependencies import get_api_data, save_transformed_to_json, transformed_data_to_database
from common.errors import error_msg

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


def transform_cv_data(data_list: list) -> list:
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=options)
    try:
        transformed_data = []
        stats_trans = {"total": 0, "valid": 0, "invalid": 0}
        
        for record in data_list:
            stats_trans["total"] += 1
            res = transform_cv_record(record, driver=driver)
            if res:
                transformed_data.append(res)
                stats_trans["valid"] += 1
            else:
                stats_trans["invalid"] += 1
        
        print(f"Transformación CV: Total {stats_trans['total']}, Válidos {stats_trans['valid']}, Inválidos {stats_trans['invalid']}")
    finally:
        driver.quit()
    
    return transformed_data


if __name__ == "__main__":
    # Recupera datos de la API
    data_list = get_api_data("cv")

    # Transforma datos
    transformed_data = transform_cv_data(data_list)

    # Guarda datos transformados a json (solo debug)
    save_transformed_to_json(transformed_data, "cv")

    # Sube datos a la BD (Independiente de lo anterior)
    transformed_data_to_database(transformed_data, "cv")