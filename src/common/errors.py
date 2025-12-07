# Configuración del logger
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import logging

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "errors.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),  # modo w sobreescribe cada ejecución
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("extractor_gal")

def error_msg(e_nombre: str, missing_fields: list):
    logger.warning(f"Estación '{e_nombre}' no tiene datos en: {', '.join(missing_fields)}")

def check_postal_code(e_nombre: str, codigo_postal_str: str) -> bool:
    # Comprueba que el codigo postal sea cifras y tenga 5
    if not (len(codigo_postal_str) == 5 and codigo_postal_str.isdigit()):
        logger.error(f"El código postal de la estación '{e_nombre}' no cumple los parámetros aceptables")
        return False
    
    codigo_postal_int = int(codigo_postal_str)
    # Comprueba que el codigo postal este en el rango aceptado en España
    if not (0 <= codigo_postal_int <= 52999):
        logger.error(f"El código postal de la estación '{e_nombre}' no está entre 00000 y 52999")
        return False
    return True      

def check_coords(e_nombre: str, lat: str, lon: str) -> bool:
    lat = int(lat)
    if not (-90 <= lat <= 90):
        logger.error(f"La latitud de la estación '{e_nombre}' no está entre -90º y 90º")
        return False
    if not (-180 <= lon <= 180):
        logger.error(f"La longitud de la estación '{e_nombre}' no está entre -180º y 180º")
        return False
    return True