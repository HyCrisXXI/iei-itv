# src/api/routes/search.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from src.database.session import get_db
from src.database.models import Estacion, Localidad, Provincia
from src.api.schemas import EstacionSchema, SearchResponse

router = APIRouter(prefix="/search", tags=["Búsqueda"])


@router.get(
    "",
    response_model=SearchResponse,
    summary="Buscar estaciones ITV",
    description="""
    Endpoint para buscar estaciones ITV con filtros opcionales.
    
    Permite filtrar por:
    - **localidad**: Nombre de la localidad
    - **cod_postal**: Código postal exacto
    - **provincia**: Nombre de la provincia
    
    Si no se especifica ningún filtro, devuelve todas las estaciones.
    """
)
async def search_stations(
    localidad: Optional[str] = Query(
        None,
        description="Nombre de la localidad a buscar",
        min_length=1,
        max_length=100,
        example="Valencia"
    ),
    cod_postal: Optional[str] = Query(
        None,
        description="Código postal exacto a buscar",
        min_length=4,
        max_length=10,
        pattern=r"^\d{4,5}$",
        example="46001"
    ),
    provincia: Optional[str] = Query(
        None,
        description="Nombre de la provincia a buscar",
        min_length=1,
        max_length=100,
        example="Valencia"
    ),
    tipo: Optional[str] = Query(
        None,
        description="Tipo de estación: Fija, Movil, Otros",
        example="Fija"
    ),
    db: Session = Depends(get_db)
) -> SearchResponse:   
    # Construir la consulta base con joins para obtener info de localidad y provincia
    query = db.query(Estacion).outerjoin(
        Localidad, Estacion.codigo_localidad == Localidad.codigo
    ).outerjoin(
        Provincia, Localidad.codigo_provincia == Provincia.codigo
    )
    
    # Aplicar filtros según los parámetros recibidos
    if localidad:
        query = query.filter(Localidad.nombre.ilike(f"%{localidad}%"))
    
    if cod_postal:
        query = query.filter(Estacion.codigo_postal == cod_postal)
    
    if provincia:
        query = query.filter(Provincia.nombre.ilike(f"%{provincia}%"))
    
    if tipo:
        query = query.filter(Estacion.tipo.ilike(f"%{tipo}%"))
    
    # Ejecutar consulta
    estaciones = query.all()
    
    # Verificar si se encontraron resultados
    if not estaciones:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron estaciones con los criterios especificados"
        )
    
    # Transformar modelos SQLAlchemy a esquemas Pydantic
    resultados = []
    for estacion in estaciones:
        # Obtener el valor del tipo (manejar ChoiceType)
        tipo_value = estacion.tipo.value if hasattr(estacion.tipo, 'value') else str(estacion.tipo)
        
        # Obtener nombres de localidad y provincia si están disponibles
        localidad_nombre = None
        provincia_nombre = None
        
        if estacion.localidad:
            localidad_nombre = estacion.localidad.nombre
            if estacion.localidad.provincia:
                provincia_nombre = estacion.localidad.provincia.nombre
        
        estacion_dict = EstacionSchema(
            cod_estacion=estacion.cod_estacion,
            nombre=estacion.nombre,
            tipo=tipo_value,
            direccion=estacion.direccion,
            codigo_postal=estacion.codigo_postal,
            latitud=estacion.latitud,
            longitud=estacion.longitud,
            descripcion=estacion.descripcion,
            horario=estacion.horario,
            contacto=estacion.contacto,
            url=estacion.url,
            codigo_localidad=estacion.codigo_localidad,
            origen_datos=estacion.origen_datos,
            localidad_nombre=localidad_nombre,
            provincia_nombre=provincia_nombre
        )
        resultados.append(estacion_dict)
    
    return SearchResponse(
        total=len(resultados),
        resultados=resultados
    )
