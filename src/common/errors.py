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
logger = logging.getLogger("extractor")

def error_msg(e_nombre: str, missing_fields: list):
    logger.error(f"Estación '{e_nombre}' incompleta -> {', '.join(missing_fields)}")

def check_postal_code(e_nombre: str, codigo_postal_str: str) -> bool:
    # Comprueba que el codigo postal sea cifras y tenga 5
    if not (len(codigo_postal_str) == 5 and codigo_postal_str.isdigit()):
        logger.error(f"Estación '{e_nombre}' descartada -> Código postal '{codigo_postal_str}' inválido (longitud/formato)")
        return False
    
    codigo_postal_int = int(codigo_postal_str)
    # Comprueba que el codigo postal este en el rango aceptado en España
    if not (0 <= codigo_postal_int <= 52999):
        logger.error(f"Estación '{e_nombre}' descartada -> Código postal '{codigo_postal_str}' fuera de rango (0-52999)")
        return False
    return True      

def check_coords(e_nombre: str, lat: float, lon: float) -> bool:
    # lat/lon son floats ya convertidos usualmente, o strings validados antes
    # Gal pasa float.
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        logger.error(f"Estación '{e_nombre}' descartada -> Coordenadas inválidas")
        return False

    if not (-90 <= lat <= 90):
        logger.error(f"Estación '{e_nombre}' descartada -> Latitud {lat} fuera de rango (-90 a 90)")
        return False
    if not (-180 <= lon <= 180):
        logger.error(f"Estación '{e_nombre}' descartada -> Longitud {lon} fuera de rango (-180 a 180)")
        return False
    return True