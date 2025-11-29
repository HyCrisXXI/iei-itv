# src/extractors/selenium_google.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

def validar_y_limpiar_entrada(direccion: str, municipio: str):
    """
    Valida y limpia los argumentos antes de iniciar la búsqueda.
    Retorna una tupla (direccion_limpia, municipio_limpio) o lanza una excepción.
    """
    # 1. Validación de tipos
    if not isinstance(direccion, str) or not isinstance(municipio, str):
        raise TypeError("Dirección y municipio deben ser cadenas de texto.")

    # 2. Limpieza de espacios
    dir_clean = direccion.strip()
    mun_clean = municipio.strip()

    # 3. Validación de contenido vacío
    if not dir_clean or not mun_clean:
        raise ValueError("La dirección o el municipio no pueden estar vacíos.")

    # 4. Limpieza de ruido (s/n, s/ nº, etc.)
    # Esto evita que Google se confunda con términos genéricos
    patron_sn = r'\b(s/nº?|s\.n\.?)\b'
    dir_clean = re.sub(patron_sn, '', dir_clean, flags=re.IGNORECASE).strip()

    # 5. Longitud mínima de seguridad (opcional, evita búsquedas absurdas)
    if len(dir_clean) < 2:
        raise ValueError(f"La dirección '{dir_clean}' es demasiado corta.")

    return dir_clean, mun_clean

def get_coords_from_google_url(url):
    """
    Extrae latitud y longitud de la URL de Google Maps.
    Formatos típicos:
    - .../place/Busqueda/@39.469,-0.377,15z/...
    - .../search/Busqueda/@39.469,-0.377,15z/...
    """
    # Patrón: busca "@" seguido de número, coma, número
    patron = r'@([-0-9.]+),([-0-9.]+)'
    match = re.search(patron, url)
    if match:
        # Convertimos a float para devolver el formato numérico correcto
        return float(match.group(1)), float(match.group(2))
    return None, None

def geolocate_google_selenium(driver, direccion: str, municipio: str):
    """
    Función principal de geolocalización (Caja Negra).
    Recibe driver, dirección y municipio. Devuelve (lat, lon) o (None, None).
    """
    # --- FASE 1: Validación y Limpieza ---
    try:
        dir_final, mun_final = validar_y_limpiar_entrada(direccion, municipio)
    except (ValueError, TypeError) as e:
        print(f"   [!] Error de validación: {e}")
        return None, None

    # --- FASE 2: Construcción de la búsqueda inteligente---
    # Estrategia: "ITV" + Municipio + Dirección
    busqueda = f"ITV {mun_final}, {dir_final}"
    if "km" in dir_final.lower():
        # Google maneja bien los Km, se lo pasamos tal cual, 
        # pero a veces ayuda añadir "España" para que no busque en otro país
        busqueda += ", España"

    # --- FASE 3: Interacción con Selenium ---
    url = "https://www.google.com/maps"
    
    try:
        driver.get(url)
        
        # Separamos esperas: corta para chequear cookies (rapidez), larga para carga de mapa (seguridad en conexión lenta)
        wait_largo = WebDriverWait(driver, 10)
        wait_corto = WebDriverWait(driver, 2)

        # 1. Gestión de cookies (si aparece)
        try:
            # Busca el botón que contenga el texto "Aceptar todo" o "Accept all"
            # Usamos wait_corto para no perder tiempo si ya están aceptadas
            accept_btn = wait_corto.until(EC.element_to_be_clickable(
                (By.XPATH, "//button//span[contains(text(), 'Aceptar todo')] | //button//span[contains(text(), 'Accept all')]")
            ))
            accept_btn.click()
            # Eliminamos el sleep fijo aquí, confiamos en el wait del siguiente paso
        except:
            # Si no aparece el botón de cookies (ya aceptadas o sesión diferente), seguimos rápido
            pass

        # 2. Buscar
        # Usamos wait_largo para asegurar que cargue incluso con mala conexión
        search_box = wait_largo.until(EC.element_to_be_clickable((By.ID, "searchboxinput")))
        search_box.clear()
        search_box.send_keys(busqueda)
        search_box.send_keys(Keys.ENTER)

        # 3. Esperar a que la URL cambie
        # Esperamos hasta que la URL contenga una arroba '@' (indicador de coords)
        wait_largo.until(EC.url_contains("@"))
        
        # Damos un tiempo mínimo para que la URL se estabilice (a veces hace pan/zoom)
        time.sleep(0.5) 

        # 4. Extraer Datos
        current_url = driver.current_url
        lat, lon = get_coords_from_google_url(current_url)
        
        if lat is not None and lon is not None:
            print(f"   [OK] {busqueda} -> ({lat}, {lon})")
            return lat, lon
        else:
            print(f"   [X] URL sin coordenadas claras: {current_url}")
            return None, None
            
    except Exception as e:
        print(f"   [!] Error buscando '{busqueda}': {e}")
        return None, None

# De aquí hacia abajo solo sirve para probar funcionamiento, la caja negra está arriba

def jsontojson():
    path = Path(__file__).resolve().parent.parent.parent / "data" / "estaciones.json"
    if not path.exists(): return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

if __name__ == "__main__":
    data = jsontojson()

    # Configuración de Selenium (esto se tiene que hacer en extractor_cv.py)
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless=new") # Modo invisible
    # options.add_argument("--start-minimized") # Modo minimizado
    options.add_argument("--start-maximized") # Modo maximizado
    options.add_argument("--disable-blink-features=AutomationControlled") 
    
    driver = webdriver.Chrome(options=options)
    # Fin configuración selenium

    final_data = []

    # Este try-finally también deberías hacerlo en extrator_cv.py (aunque cambiandolo un poco)
    try:
        for item in data:
            # Filtro básico
            tipo = item.get("TIPO ESTACIÓN", "")
            if "Móvil" in tipo or "Agrícola" in tipo:
                continue # No buscamos direcciones móviles o agrícolas

            municipio = item.get("MUNICIPIO", "")
            direccion = item.get("DIRECCIÓN", "")
            
            print(f"Procesando: {direccion}, {municipio}...")
            
            # Llamada a la caja negra
            lat, lon = geolocate_google_selenium(driver, direccion, municipio)
            
            if lat and lon:
                item["latitud"] = lat
                item["longitud"] = lon
                final_data.append(item)
            else:
                print(f"   [FALLO] No encontrado o inválido: {municipio}")
    finally:
        driver.quit()

    # Guardar
    out = Path(__file__).resolve().parent / "cv_google.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)