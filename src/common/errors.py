# Configuración del logger
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import logging

REJECTED_RECORDS: list[dict] = []
REPAIRED_RECORDS: list[dict] = []

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

def _normalize(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    return str(value).strip() or fallback


def register_rejection(
    source: str | None,
    nombre: str | None,
    localidad: str | None,
    motivo: str,
) -> None:
    entry = {
        "fuente": _normalize(source, "desconocida"),
        "nombre": _normalize(nombre, "Desconocida"),
        "localidad": _normalize(localidad, "Sin localidad"),
        "motivo": motivo,
    }
    REJECTED_RECORDS.append(entry)


def register_repair(
    source: str | None,
    nombre: str | None,
    localidad: str | None,
    motivo: str,
    operacion: str,
) -> None:
    entry = {
        "fuente": _normalize(source, "desconocida"),
        "nombre": _normalize(nombre, "Desconocida"),
        "localidad": _normalize(localidad, "Sin localidad"),
        "motivo": motivo,
        "operacion": operacion,
    }
    REPAIRED_RECORDS.append(entry)


def consume_error_logs() -> dict:
    data = {
        "rechazados": REJECTED_RECORDS.copy(),
        "reparados": REPAIRED_RECORDS.copy(),
    }
    REJECTED_RECORDS.clear()
    REPAIRED_RECORDS.clear()
    return data


def reset_error_logs() -> None:
    REJECTED_RECORDS.clear()
    REPAIRED_RECORDS.clear()


def error_msg(e_nombre: str, missing_fields: list):
    logger.error(f"Estación '{e_nombre}' incompleta -> {', '.join(missing_fields)}")


def check_postal_code(
    e_nombre: str,
    codigo_postal_str: str,
    *,
    source: str | None = None,
    localidad: str | None = None,
) -> bool:
    # Comprueba que el codigo postal sea cifras y tenga 5
    if not (len(codigo_postal_str) == 5 and codigo_postal_str.isdigit()):
        motivo = f"Código postal '{codigo_postal_str}' inválido (longitud/formato)"
        logger.error(f"Estación '{e_nombre}' descartada -> {motivo}")
        register_rejection(source, e_nombre, localidad, motivo)
        return False
    
    codigo_postal_int = int(codigo_postal_str)
    # Comprueba que el codigo postal este en el rango aceptado en España
    if not (0 <= codigo_postal_int <= 52999):
        motivo = f"Código postal '{codigo_postal_str}' fuera de rango (0-52999)"
        logger.error(f"Estación '{e_nombre}' descartada -> {motivo}")
        register_rejection(source, e_nombre, localidad, motivo)
        return False
    return True      

def check_coords(
    e_nombre: str,
    lat: float,
    lon: float,
    *,
    source: str | None = None,
    localidad: str | None = None,
) -> bool:
    # lat/lon son floats ya convertidos usualmente, o strings validados antes
    # Gal pasa float.
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        motivo = "Coordenadas inválidas"
        logger.error(f"Estación '{e_nombre}' descartada -> {motivo}")
        register_rejection(source, e_nombre, localidad, motivo)
        return False

    if not (-90 <= lat <= 90):
        motivo = f"Latitud {lat} fuera de rango (-90 a 90)"
        logger.error(f"Estación '{e_nombre}' descartada -> {motivo}")
        register_rejection(source, e_nombre, localidad, motivo)
        return False
    if not (-180 <= lon <= 180):
        motivo = f"Longitud {lon} fuera de rango (-180 a 180)"
        logger.error(f"Estación '{e_nombre}' descartada -> {motivo}")
        register_rejection(source, e_nombre, localidad, motivo)
        return False
    return True