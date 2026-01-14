from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.wrappers.wrapper_gal import csvtojson


router = APIRouter(
    prefix="/wrappers/gal",
    tags=["Wrapper Galicia"]
)


@router.get(
    "/estaciones",
    summary="Obtener estaciones de la fuente Galicia",
    description="Convierte el CSV en un JSON unificado.",
    response_model=List[Dict[str, Any]]
)
def get_gal_stations() -> List[Dict[str, Any]]:
    try:
        return csvtojson()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="No se pudo obtener la información original de Galicia"
        ) from exc