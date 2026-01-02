from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.wrappers.wrapper_cat import xmltojson


router = APIRouter(
    prefix="/wrappers/cat",
    tags=["Wrapper Cataluña"]
)


@router.get(
    "/estaciones",
    summary="Obtener estaciones de la fuente Cataluña",
    description="Transforma el XML oficial en una representación JSON lista para el backend.",
    response_model=List[Dict[str, Any]]
)
def get_cat_stations() -> List[Dict[str, Any]]:
    try:
        return xmltojson()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="No se pudo obtener la información original de Cataluña"
        ) from exc