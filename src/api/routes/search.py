# src/api/routes/search.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
from typing import Optional

from src.database.session import get_db
from src.database.models import Estacion, Localidad, Provincia
from src.api.schemas import EstacionSchema, SearchResponse

router = APIRouter(prefix="/estaciones", tags=["Estaciones"])


@router.get(
    "",
    response_model=SearchResponse,
    summary="Listar y buscar estaciones ITV",
    description="""
    Recurso principal para obtener estaciones ITV con filtros opcionales.
    
    Permite filtrar por:
    - **localidad**: Nombre de la localidad
    - **cod_postal**: Código postal exacto
    - **provincia**: Nombre de la provincia
    - **tipo**: Tipo de estación (Fija, Movil, Otros)
    
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
        query = query.filter(cast(Estacion.tipo, String).ilike(f"%{tipo}%"))
    
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


@router.get(
    "/{cod_estacion}",
    response_model=EstacionSchema,
    summary="Obtener una estación por su código",
    description="Devuelve los datos completos de una estación ITV identificada por su código único."
)
async def get_station(
    cod_estacion: int,
    db: Session = Depends(get_db)
) -> EstacionSchema:
    estacion = db.query(Estacion).filter(Estacion.cod_estacion == cod_estacion).first()

    if not estacion:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró la estación con código {cod_estacion}"
        )

    tipo_value = estacion.tipo.value if hasattr(estacion.tipo, 'value') else str(estacion.tipo)

    localidad_nombre = None
    provincia_nombre = None
    if estacion.localidad:
        localidad_nombre = estacion.localidad.nombre
        if estacion.localidad.provincia:
            provincia_nombre = estacion.localidad.provincia.nombre

    return EstacionSchema(
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
