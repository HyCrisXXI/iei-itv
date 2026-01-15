# src/extractors/extractor_cv.py
import unicodedata
import sys
import re
import time
from difflib import get_close_matches
from selenium import webdriver
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.extractors.selenium_cv import geolocate_google_selenium
from src.common.dependencies import get_api_data, save_transformed_to_json, transformed_data_to_database
from src.common.errors import error_msg, register_rejection, register_repair, check_postal_code
from src.common.validators import (
    is_valid_horario, 
    is_valid_email, 
    choose_best_value,
    merge_duplicate_records
)

#Normaliza provincias automáticamente corrigiendo errores
PROVINCIAS_VALIDAS = ["valencia","alicante","castellon"]


# Definir validadores específicos para CV
CV_FIELD_VALIDATORS = {
    "HORARIOS": is_valid_horario,
    "CORREO": is_valid_email,
}
SOURCE_TAG = "cv"


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
    
    # Validación robusta de horario con Regex
    municipio = record.get("MUNICIPIO")
    def _reject(reason: str, *, nombre: str | None = None):
        context_name = nombre or build_station_name(municipio) or record.get("DIRECCIÓN")
        register_rejection(SOURCE_TAG, context_name, municipio, reason)

    if horario:
        # Busca patrones H:MM o HH:MM
        times = re.findall(r'(\d{1,2}):(\d{2})', horario)
        for h_str, m_str in times:
            try:
                h = int(h_str)
                m = int(m_str)
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    # Fuera de rango
                    print(f"   [!] Horario inválido detectado: {h}:{m} en '{horario}'")
                    _reject(f"Horario inválido: {horario}")
                    return None
            except ValueError:
                _reject(f"Horario inválido: {horario}")
                return None

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
        codigo_postal = record.get("C.POSTAL")
        cod_postal_string = str(codigo_postal) if codigo_postal else None
        p_cod = cod_postal_string[:2] if cod_postal_string else None

        nombre = build_station_name(municipio)

        if not cod_postal_string:
            error_msg(nombre or municipio or "Desconocida", ["codigo_postal"])
            _reject("Código postal obligatorio", nombre=nombre)
            return None

        if not check_postal_code(
            nombre or municipio or "Desconocida",
            cod_postal_string,
            source=SOURCE_TAG,
            localidad=municipio,
        ):
            return None

        # Validación de campos obligatorios para estaciones fijas
        if not provincia:
            error_msg(nombre, ["provincia"])
            _reject("Provincia no reconocida", nombre=nombre)
            return None
        if not municipio:
            error_msg(nombre, ["municipio"])
            _reject("Municipio obligatorio", nombre=nombre)
            return None

        # Geolocalización mediante Selenium
        lat, lon = geolocate_google_selenium(driver, direccion, municipio)
        # Solo comprobamos latitud, ya que el método devuelve ambas o ninguna
        if not lat:
            error_msg(nombre, ["latitud/longitud"])
            _reject("No se pudieron obtener coordenadas válidas", nombre=nombre)
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
        codigo_postal = record.get("C.POSTAL")
        if codigo_postal:
            cod_postal_string = str(codigo_postal)
            if not check_postal_code(
                direccion or "Desconocida",
                cod_postal_string,
                source=SOURCE_TAG,
                localidad=municipio,
            ):
                return None
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
    # Paso 1: Fusionar registros duplicados antes de transformar
    print(f"   [*] Registros originales: {len(data_list)}")

    def _log_duplicate_merge(key: str, records: list[dict]) -> None:
        if not key or key.startswith("_unnamed"):
            return
        municipios = []
        for record in records:
            municipio = record.get("MUNICIPIO")
            if isinstance(municipio, str):
                normalized = municipio.strip()
                if normalized:
                    municipios.append(normalized)
        if len(municipios) < 2:
            return
        unique_display = set(municipios)
        unique_normalized = {m.lower() for m in municipios}
        if len(unique_display) > 1 and len(unique_normalized) == 1:
            municipio_final = municipios[0]
            nombre = build_station_name(municipio_final)
            register_repair(
                SOURCE_TAG,
                nombre or f"Estación {key}",
                municipio_final,
                "Municipio duplicado con distinta capitalización",
                "Municipio normalizado durante la fusión de duplicados",
            )

    merged_data = merge_duplicate_records(
        data_list,
        "Nº ESTACIÓN",
        CV_FIELD_VALIDATORS,
        on_merge=_log_duplicate_merge,
    )
    print(f"   [*] Registros tras fusión: {len(merged_data)}")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=options)
    try:
        transformed_data = []
        stats_trans = {"total": 0, "valid": 0, "invalid": 0}
        
        for record in merged_data:
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