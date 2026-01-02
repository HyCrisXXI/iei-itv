from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.wrappers.wrapper_cv import jsontojson


router = APIRouter(
    prefix="/wrappers/cv",
    tags=["Wrapper Comunitat Valenciana"]
)


@router.get(
    "/estaciones",
    summary="Obtener estaciones de la fuente Comunitat Valenciana",
    description="Publica el JSON autonómico sin transformar para alimentar el sistema.",
    response_model=List[Dict[str, Any]]
)
def get_cv_stations() -> List[Dict[str, Any]]:
    try:
        return jsontojson()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="No se pudo obtener la información original de la Comunitat Valenciana"
        ) from exc