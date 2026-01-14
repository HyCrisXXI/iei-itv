from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import Estacion, Localidad, Provincia
from src.api.schemas import EstacionSchema, SearchResponse


router = APIRouter(prefix="/load", tags=["Carga de Estaciones"])

# Comunidades con pipelines implementados en el sistema
# Nota: el valor coincide con el campo "origen_datos" almacenado en la BD
VALID_SOURCES = {"gal", "cv", "cat"}


@router.get(
	"",
	response_model=SearchResponse,
	summary="Listar estaciones por comunidad autónoma",
	description="Devuelve todas las estaciones registradas en la base de datos para la comunidad seleccionada.",
)
async def get_stations_by_source(
	fuente: str = Query(
		...,
		description="Código de la comunidad autónoma (gal, cv o cat)",
		example="gal",
	),
	db: Session = Depends(get_db),
) -> SearchResponse:
	fuente_normalizada = fuente.strip().lower()
	if fuente_normalizada not in VALID_SOURCES:
		raise HTTPException(
			status_code=400,
			detail="La comunidad seleccionada no es válida. Valores permitidos: gal, cv, cat",
		)

	# Consulta todas las estaciones cuyo origen coincide con la comunidad seleccionada
	estaciones = db.query(Estacion).filter(Estacion.origen_datos == fuente_normalizada).all()

	if not estaciones:
		raise HTTPException(
			status_code=404,
			detail="No hay estaciones almacenadas para la comunidad seleccionada",
		)

	resultados = []
	for estacion in estaciones:
		# ChoiceType puede exponer Enum o string según el backend, de ahí la comprobación
		tipo_value = estacion.tipo.value if hasattr(estacion.tipo, "value") else str(estacion.tipo)

		localidad_nombre = None
		provincia_nombre = None

		if estacion.localidad:
			# Traemos el nombre de la localidad para enriquecer la respuesta
			localidad_nombre = estacion.localidad.nombre
			if estacion.localidad.provincia:
				# Igual para la provincia, si existe relación cargada
				provincia_nombre = estacion.localidad.provincia.nombre

		resultados.append(
			EstacionSchema(
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
				provincia_nombre=provincia_nombre,
			)
		)

	return SearchResponse(total=len(resultados), resultados=resultados)


@router.delete(
	"",
	summary="Borrar todo el almacén de datos",
	description="Elimina estaciones, localidades y provincias almacenadas en la base de datos.",
)
async def delete_storage(db: Session = Depends(get_db)) -> dict:
	# Se elimina siguiendo la jerarquía para evitar claves foráneas huérfanas
	estaciones_eliminadas = db.query(Estacion).delete(synchronize_session=False)
	# Localidades dependen de provincias, por eso se borran en segundo lugar
	localidades_eliminadas = db.query(Localidad).delete(synchronize_session=False)
	# Por último provincias; si no hubiera localidades relacionadas, la operación es segura
	provincias_eliminadas = db.query(Provincia).delete(synchronize_session=False)
	db.commit()

	return {
		"message": "Almacén reiniciado correctamente",
		"eliminados": {
			"estaciones": estaciones_eliminadas,
			"localidades": localidades_eliminadas,
			"provincias": provincias_eliminadas,
		},
	}