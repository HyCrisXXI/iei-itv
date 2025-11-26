# src/extractors/extractor_cv.py
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from geopy.geocoders import Nominatim
import time
import re
import unicodedata
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from database.models import TipoEstacion, Provincia, Localidad, Estacion
from database.session import get_db, create_db_and_tables


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


def scrape_sitval_centros():
    """
    Scrape sitval.com/centros y extrae municipios, códigos postales y provincias.
    Devuelve una tupla (municipios_list, codigos_postales_list, provincias_list) con listas paralelas.
    """
    url = "https://sitval.com/centros"
    
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(url)
        
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "table")))
        
        time.sleep(2)
        
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
    finally:
        driver.quit()
    
    datos = []
    
    # Buscar todos los h1 que contienen "Estaciones fijas"
    h1_elements = soup.find_all('h1')
    
    for h1 in h1_elements:
        if 'Estaciones fijas' in h1.get_text():
            # Encontrar todos los h2 después de este h1
            current = h1.find_next_sibling()
            
            while current:
                if current.name == 'h2':
                    provincia_text = current.get_text(strip=True)
                    
                    if provincia_text in ['Alicante', 'Castellón', 'Castelló', 'València']:
                        provincia_actual = provincia_text
                        if provincia_actual == 'Castelló':
                            provincia_actual = 'Castellón'
                        
                        # Encontrar la tabla después de este h2
                        tabla = current.find_next('table')
                        if tabla:
                            rows = tabla.find_all('tr')
                            for row in rows:
                                cols = row.find_all('td')
                                
                                if len(cols) < 2:
                                    continue
                                
                                row_data = [col.get_text(strip=True) for col in cols]
                                
                                municipio = row_data[0].strip()
                                codigo_postal = row_data[1].strip()
                                
                                if municipio and codigo_postal and re.match(r'^\d{5}$', codigo_postal):
                                    datos.append({
                                        'Municipio': municipio,
                                        'Código Postal': codigo_postal,
                                        'Provincia': provincia_actual
                                    })
                
                current = current.find_next_sibling()
                
                # Parar si encontramos otro h1
                if current and current.name == 'h1':
                    break
    
    # Si no encontramos datos con h2, intentar otra estrategia usando códigos postales
    if not datos:
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                
                if len(cols) < 2:
                    continue
                
                row_data = [col.get_text(strip=True) for col in cols]
                
                municipio = row_data[0].strip()
                codigo_postal = row_data[1].strip()
                
                if municipio and codigo_postal and re.match(r'^\d{5}$', codigo_postal):
                    # Determinar provincia por código postal
                    cp_num = int(codigo_postal[:2])
                    if cp_num == 3:
                        provincia = 'Alicante'
                    elif cp_num == 12:
                        provincia = 'Castellón'
                    elif cp_num == 46:
                        provincia = 'València'
                    else:
                        provincia = 'Desconocida'
                    
                    datos.append({
                        'Municipio': municipio,
                        'Código Postal': codigo_postal,
                        'Provincia': provincia
                    })
    
    # Eliminar duplicados manteniendo el orden
    municipios_unicos = {}
    for item in datos:
        key = (item['Municipio'], item['Código Postal'], item['Provincia'])
        if key not in municipios_unicos:
            municipios_unicos[key] = item
    
    # Crear listas separadas
    municipios_list = [m for m, cp, p in municipios_unicos.keys()]
    codigos_postales_list = [cp for m, cp, p in municipios_unicos.keys()]
    provincias_list = [p for m, cp, p in municipios_unicos.keys()]
    
    return (municipios_list, codigos_postales_list, provincias_list)


def extract_domain_from_email(email: str) -> str | None:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1]


geolocator = Nominatim(user_agent="extractor_cv")


def get_coords(direccion: str, municipio: str = "", provincia: str = ""):
    """
    Intenta geocodificar usando varias estrategias progresivas.
    """
    if not direccion and not municipio:
        return None, None

    # Estrategias de geocodificación en orden de especificidad
    strategies = [
        direccion,  # Dirección completa
        f"{direccion}, {municipio}" if direccion and municipio else None,  # Dirección + municipio
        f"{direccion}, {municipio}, {provincia}" if direccion and municipio and provincia else None,  # Dirección + municipio + provincia
        f"{municipio}, {provincia}" if municipio and provincia else None,  # Solo municipio + provincia
        municipio if municipio else None,  # Solo municipio
    ]

    for strategy in strategies:
        if not strategy:
            continue
        
        try:
            loc = geolocator.geocode(strategy, timeout=10)
            time.sleep(0.5)
            if loc:
                return loc.latitude, loc.longitude
        except Exception:
            pass

    return None, None

def normalize_station_type(tipo: str | None) -> str:
    if not tipo:
        return "Otros"

    cleaned = tipo.replace("Estación", "").strip()

    return cleaned if cleaned else "Otros"

def error_msg(e_nombre: str, missing_fields):
    print(f"Estación '{e_nombre}' no tiene datos en: {', '.join(missing_fields)}")


def transform_cv_record(record: dict, station_names_map: dict) -> dict | None:
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

    # Normaliza tipo para mantener consistencia en BD
    transformed["tipo_estacion"] = normalize_station_type(
        transformed.get("tipo_estacion") or tipo_raw
    )
    
    cod_postal_string = str(transformed.get("codigo_postal", ""))
    transformed["p_cod"] = cod_postal_string[:2] if cod_postal_string else None

    correo = transformed.get("contacto")
    transformed["url"] = extract_domain_from_email(correo)

    direccion = transformed.get("direccion")
    municipio = record.get("MUNICIPIO", "")
    provincia = record.get("PROVINCIA", "")
    lat, lon = get_coords(direccion, municipio, provincia)
    transformed["lat"] = lat
    transformed["lon"] = lon

    # Determina un nombre estable incluso sin municipio/código postal
    cod_postal = record.get("C.POSTAL")
    station_code = str(record.get("Nº ESTACIÓN", "")).strip()
    nombre_base = None
    
    if cod_postal:
        cod_postal_str = str(cod_postal).strip()
        if cod_postal_str in station_names_map:
            nombre_sitval = station_names_map[cod_postal_str]
            nombre_base = nombre_sitval

    if not nombre_base and station_code:
        nombre_base = station_code
    if not nombre_base and municipio:
        nombre_base = municipio
    if not nombre_base:
        nombre_base = provincia or "Desconocida"

    transformed["nombre"] = f"ITV {nombre_base} SITVAL".strip()

    # Validación de campos requeridos y mensajes de error
    required_fields = [
        "direccion", "codigo_postal", "lat", "lon", "horario", "contacto", "url"
    ]
    missing_fields = []
    for field in required_fields:
        value = transformed.get(field)
        if value is None or value == "":
            missing_fields.append(field)
    if missing_fields:
        error_msg(transformed.get("nombre", "Desconocida"), missing_fields)

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


def insert_transformed_to_db(transformed_list: list) -> tuple[int, int]:
    """Insert transformed CV records into the database without additional validation.
    Returns (inserted_count, skipped_count).
    """
    create_db_and_tables()
    inserted = 0
    skipped = 0

    with next(get_db()) as session:
        prov_cache = {}
        loc_cache = {}
        est_cache = {}

        for rec in transformed_list:
            nombre = rec.get('nombre') or 'Desconocida'
            p_nombre = rec.get('p_nombre')
            l_nombre = rec.get('l_nombre')
            p_cod = rec.get('p_cod')

            # Provincia
            prov = prov_cache.get(p_nombre)
            if prov is None:
                prov = session.query(Provincia).filter_by(nombre=p_nombre).first()
                if not prov:
                    prov_args = {"nombre": p_nombre}
                    if p_cod:
                        try:
                            prov_args["codigo"] = int(str(p_cod))
                        except Exception:
                            prov_args["codigo"] = None
                    prov = Provincia(**prov_args)
                    session.add(prov)
                    session.flush()
                prov_cache[p_nombre] = prov

            # Localidad
            loc_key = (l_nombre, prov.codigo)
            loc = loc_cache.get(loc_key)
            if loc is None:
                loc = session.query(Localidad).filter_by(nombre=l_nombre, codigo_provincia=prov.codigo).first()
                if loc is None:
                    loc = Localidad(nombre=l_nombre, codigo_provincia=prov.codigo)
                    session.add(loc)
                    session.flush()
                loc_cache[loc_key] = loc

            # Estacion duplicate check
            est_key = (nombre, loc.codigo)
            if est_key in est_cache:
                skipped += 1
                continue
            existing = session.query(Estacion).filter_by(nombre=nombre, codigo_localidad=loc.codigo).first()
            if existing:
                est_cache[est_key] = existing
                skipped += 1
                continue

            # Map and insert
            codigo_postal = rec.get('codigo_postal')
            try:
                if codigo_postal is not None:
                    codigo_postal = int(str(codigo_postal).strip())
            except Exception:
                codigo_postal = None

            estacion_kwargs = {
                'nombre': nombre,
                'tipo': _map_tipo_enum(rec.get('tipo_estacion') or rec.get('tipo')),
                'codigo_localidad': loc.codigo,
                'origen_datos': 'cv',
                'direccion': rec.get('direccion'),
                'codigo_postal': codigo_postal,
                'latitud': rec.get('lat'),
                'longitud': rec.get('lon'),
                'horario': rec.get('horario'),
                'contacto': rec.get('contacto'),
                'url': rec.get('url'),
            }

            estacion = Estacion(**estacion_kwargs)
            session.add(estacion)
            est_cache[est_key] = estacion
            inserted += 1

        session.commit()

    return inserted, skipped

if __name__ == "__main__":
    # Obtener nombres reales de sitval
    municipios, codigos_postales, provincias = scrape_sitval_centros()
    station_names_map = dict(zip(codigos_postales, municipios))

    data_list = jsontojson()
    transformed_data = [transform_cv_record(record, station_names_map) for record in data_list]
    transformed_data = [t for t in transformed_data if t is not None]
    out_path = Path(__file__).resolve().parent / "cv.json"
    with out_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(transformed_data, jsonfile, indent=4, ensure_ascii=False)

    # Automatic DB insertion (no validation). WARNING: this will perform writes.
    try:
        inserted, skipped = insert_transformed_to_db(transformed_data)
        print(f"DB insertion completed. Inserted: {inserted}, Skipped: {skipped}")
    except Exception as e:
        print(f"Error inserting data into DB: {e}")