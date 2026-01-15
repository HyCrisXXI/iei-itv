from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import Estacion, Localidad, Provincia
from src.api.schemas import (
	EstacionSchema,
	SearchResponse,
	LoadRequest,
	LoadProcessResponse,
	FuenteCargaDetalle,
	RegistroReparadoSchema,
	RegistroRechazadoSchema,
)
from src.common.db_storage import save_stations
from src.common.errors import consume_error_logs, reset_error_logs
from src.wrappers.wrapper_gal import csvtojson
from src.wrappers.wrapper_cv import jsontojson
from src.wrappers.wrapper_cat import xmltojson
from src.extractors.extractor_gal import transform_gal_data
from src.extractors.extractor_cv import transform_cv_data
from src.extractors.extractor_cat import transform_cat_data


router = APIRouter(prefix="/load", tags=["Carga de Estaciones"])

# Comunidades con pipelines implementados en el sistema
# Nota: el valor coincide con el campo "origen_datos" almacenado en la BD
VALID_SOURCES = {"gal", "cv", "cat"}

RAW_FETCHERS = {
	"gal": csvtojson,
	"cv": jsontojson,
	"cat": xmltojson,
}

TRANSFORMERS = {
	"gal": transform_gal_data,
	"cv": transform_cv_data,
	"cat": transform_cat_data,
}


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
			# Traemos el nombre de la localidad
			localidad_nombre = estacion.localidad.nombre
			if estacion.localidad.provincia:
				# Igual para la provincia
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


@router.post(
	"/run",
	response_model=LoadProcessResponse,
	summary="Ejecutar pipelines de carga",
	description=(
		"Obtiene, transforma y guarda los datos de las comunidades seleccionadas, "
		"retornando un resumen de la operación."
	),
)
async def run_load_pipelines(payload: LoadRequest) -> LoadProcessResponse:
	seen: set[str] = set()
	fuentes_normalizadas: List[str] = []
	for fuente in payload.fuentes:
		if not fuente:
			continue
		key = fuente.strip().lower()
		if not key or key in seen:
			continue
		seen.add(key)
		fuentes_normalizadas.append(key)

	if not fuentes_normalizadas:
		raise HTTPException(status_code=400, detail="No se proporcionaron comunidades válidas para cargar")

	invalid = [src for src in fuentes_normalizadas if src not in VALID_SOURCES]
	if invalid:
		raise HTTPException(
			status_code=400,
			detail=f"Las siguientes comunidades no son válidas: {', '.join(invalid)}",
		)

	result = await run_in_threadpool(_process_sources_pipeline, fuentes_normalizadas)
	return LoadProcessResponse(**result)


def _process_sources_pipeline(fuentes: List[str]) -> dict:
	detalles: List[FuenteCargaDetalle] = []
	total_insertados = 0
	total_duplicados = 0
	total_rechazados = 0
	reparados_global: List[RegistroReparadoSchema] = []
	rechazados_global: List[RegistroRechazadoSchema] = []

	for fuente in fuentes:
		detalle = _process_single_source(fuente)
		detalles.append(detalle)
		total_insertados += detalle.insertados
		total_duplicados += detalle.duplicados
		total_rechazados += detalle.rechazados_transformacion + len(detalle.errores_guardado)
		reparados_global.extend(detalle.reparados)
		rechazados_global.extend(detalle.rechazados)

	return {
		"total_fuentes": len(detalles),
		"total_insertados": total_insertados,
		"total_duplicados": total_duplicados,
		"total_rechazados": total_rechazados,
		"detalles": detalles,
		"reparados": reparados_global,
		"rechazados": rechazados_global,
	}


def _process_single_source(fuente: str) -> FuenteCargaDetalle:
	try:
		fetcher = RAW_FETCHERS[fuente]
		transformer = TRANSFORMERS[fuente]
		reset_error_logs()
		raw_records = fetcher()
		transformed_records = transformer(raw_records)
		log_data = consume_error_logs()
		reparados = [RegistroReparadoSchema(**entry) for entry in log_data["reparados"]]
		rechazados = [RegistroRechazadoSchema(**entry) for entry in log_data["rechazados"]]
		stats = save_stations(transformed_records, fuente)
		errores_guardado = [str(err) for err in stats.get("errors", [])]

		return FuenteCargaDetalle(
			fuente=fuente,
			registros_origen=len(raw_records),
			registros_transformados=len(transformed_records),
			rechazados_transformacion=len(rechazados),
			insertados=stats.get("inserted", 0),
			duplicados=stats.get("duplicates", 0),
			errores_guardado=errores_guardado,
			reparados=reparados,
			rechazados=rechazados,
		)
	except Exception as exc:  # pylint: disable=broad-except
		reset_error_logs()
		return FuenteCargaDetalle(
			fuente=fuente,
			registros_origen=0,
			registros_transformados=0,
			rechazados_transformacion=0,
			insertados=0,
			duplicados=0,
			errores_guardado=[f"Error procesando la fuente: {exc}"],
			reparados=[],
			rechazados=[],
		)