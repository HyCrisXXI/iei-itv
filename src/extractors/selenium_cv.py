# src/extractors/selenium_google.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import sys
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
    patron_sn = r'\b(s/nº?|s\.n\.?)\b'
    dir_clean = re.sub(patron_sn, '', dir_clean, flags=re.IGNORECASE).strip()

    # 5. Longitud mínima de seguridad
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
    # Estrategia: Priorizar dirección exacta + municipio
    busqueda = f"{direccion}, {municipio}, España" 

    # --- FASE 3: Interacción con Selenium ---
    url = "https://www.google.com/maps"
    
    try:
        # wait_largo para elementos importantes (searchbox)
        wait_largo = WebDriverWait(driver, 10) 
        # wait_corto para elementos opcionales / rápidos
        wait_corto = WebDriverWait(driver, 1)

        # Solo navegar y gestionar cookies si no estamos ya en Maps
        if "google.com/maps" not in driver.current_url:
            driver.get(url)
            
            # 1. Gestión de cookies (Prioridad: Rechazar -> Aceptar)
            if "consent.google" in driver.current_url or len(driver.find_elements(By.XPATH, "//form//button")) > 0:
                try:
                    # Intentar buscar el botón de "Rechazar todo"
                    reject_btn = wait_corto.until(EC.element_to_be_clickable(
                        (By.XPATH, "//button//span[contains(text(), 'Rechazar todo')] | //button//div[contains(text(), 'Rechazar todo')]")
                    ))
                    reject_btn.click()
                except:
                    # Si falla, intentar "Aceptar todo"
                    try:
                        accept_btn = wait_corto.until(EC.element_to_be_clickable(
                            (By.XPATH, "//button//span[contains(text(), 'Aceptar todo')] | //button//span[contains(text(), 'Accept all')] | //button//div[contains(text(), 'Aceptar todo')]")
                        ))
                        accept_btn.click()
                    except:
                        pass
        
        # 2. Buscar
        try:
            search_box = wait_corto.until(EC.element_to_be_clickable((By.ID, "searchboxinput")))
        except:
            search_box = wait_largo.until(EC.element_to_be_clickable((By.NAME, "q")))

        search_box.clear()
        search_box.send_keys(busqueda)
        
        # Capturamos coordenadas previas para detectar cambio real de mapa
        prev_lat, prev_lon = get_coords_from_google_url(driver.current_url)
        previous_url = driver.current_url
        search_box.send_keys(Keys.ENTER)

        # 3. Esperar confirmación de búsqueda (Cambio REAL de coordenadas)
        # La URL cambia rápido (query string), pero las coordenadas (@...) tardan más.
        # Esperamos explícitamente a que las coordenadas sean distintas a las anteriores.
        def coords_have_changed(driver):
            new_lat, new_lon = get_coords_from_google_url(driver.current_url)
            # Si no hay coords nuevas (quizás cargando), seguimos esperando
            if new_lat is None or new_lon is None:
                return False
            # Si no había coords previas (pantalla inicio), cualquier coord nueva vale
            if prev_lat is None or prev_lon is None:
                return True
            # Comparamos con margen (epsilon) para detectar movimiento
            return abs(new_lat - prev_lat) > 0.0001 or abs(new_lon - prev_lon) > 0.0001

        try:
            wait_largo.until(coords_have_changed)
        except:
             pass
        
        current_url = driver.current_url

        # Si estamos en una lista de resultados (/search/), intentamos clicar el primero
        if "/search/" in current_url and "/place/" not in current_url:
            try:
                # Buscar el primer enlace que contenga 'place' y darle click
                first_result = wait_corto.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a[href*='/maps/place/']")
                ))
                first_result.click()
                try: 
                    wait_corto.until(EC.url_changes(current_url)) 
                except: pass
            except:
                pass

        # 4. Validar estamos en /place/ para precisión máxima
        current_url = driver.current_url

        # 5. Extraer Datos
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