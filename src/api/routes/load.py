from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
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
	RegistroIncidenciaSchema,
	EstadoIncidencia,
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
	# Contadores previos para informar al usuario
	estaciones_count = db.query(Estacion).count()
	localidades_count = db.query(Localidad).count()
	provincias_count = db.query(Provincia).count()

	truncate_statements = (
		"TRUNCATE TABLE estaciones RESTART IDENTITY CASCADE",
		"TRUNCATE TABLE localidades RESTART IDENTITY CASCADE",
		"TRUNCATE TABLE provincias RESTART IDENTITY CASCADE",
	)
	for stmt in truncate_statements:
		db.execute(text(stmt))
	
	db.commit()

	return {
		"message": "Almacén reiniciado correctamente",
		"eliminados": {
			"estaciones": estaciones_count,
			"localidades": localidades_count,
			"provincias": provincias_count,
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
	incidencias_global: List[RegistroIncidenciaSchema] = []

	for fuente in fuentes:
		detalle = _process_single_source(fuente)
		detalles.append(detalle)
		total_insertados += detalle.insertados
		total_duplicados += detalle.duplicados
		total_rechazados += detalle.rechazados_transformacion + len(detalle.errores_guardado)
		reparados_global.extend(detalle.reparados)
		rechazados_global.extend(detalle.rechazados)
		incidencias_global.extend(detalle.incidencias)

	return {
		"total_fuentes": len(detalles),
		"total_insertados": total_insertados,
		"total_duplicados": total_duplicados,
		"total_rechazados": total_rechazados,
		"detalles": detalles,
		"reparados": reparados_global,
		"rechazados": rechazados_global,
		"incidencias": incidencias_global,
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
		rechazos_transformacion = [RegistroRechazadoSchema(**entry) for entry in log_data["rechazados"]]
		incidencias: List[RegistroIncidenciaSchema] = [
			RegistroIncidenciaSchema(
				fuente=entry.fuente,
				nombre=entry.nombre,
				localidad=entry.localidad,
				motivo=entry.motivo,
				estado=EstadoIncidencia.reparado,
				accion=entry.operacion,
			)
			for entry in reparados
		]
		incidencias.extend(
			[
				RegistroIncidenciaSchema(
					fuente=entry.fuente,
					nombre=entry.nombre,
					localidad=entry.localidad,
					motivo=entry.motivo,
					estado=EstadoIncidencia.rechazado,
					accion=None,
				)
				for entry in rechazos_transformacion
			]
		)
		stats = save_stations(transformed_records, fuente)
		errores_guardado_raw = stats.get("errors", [])
		rechazos_guardado: List[RegistroRechazadoSchema] = []
		errores_guardado: List[str] = []
		for err in errores_guardado_raw:
			if isinstance(err, dict):
				nombre_err = err.get("nombre") or "Desconocida"
				localidad_err = err.get("localidad")
				motivo_err = err.get("motivo") or "Error al guardar"
			else:
				nombre_err = "Desconocida"
				localidad_err = None
				motivo_err = str(err)
			errores_guardado.append(motivo_err)
			rechazos_guardado.append(
				RegistroRechazadoSchema(
					fuente=fuente,
					nombre=nombre_err,
					localidad=localidad_err,
					motivo=motivo_err,
				)
			)
		incidencias.extend(
			[
				RegistroIncidenciaSchema(
					fuente=entry.fuente,
					nombre=entry.nombre,
					localidad=entry.localidad,
					motivo=entry.motivo,
					estado=EstadoIncidencia.rechazado,
					accion="Descartado al guardar en BD",
				)
				for entry in rechazos_guardado
			]
		)
		rechazados = rechazos_transformacion + rechazos_guardado
		rechazados_transformacion = len(rechazos_transformacion)

		return FuenteCargaDetalle(
			fuente=fuente,
			registros_origen=len(raw_records),
			registros_transformados=len(transformed_records),
			rechazados_transformacion=rechazados_transformacion,
			insertados=stats.get("inserted", 0),
			duplicados=stats.get("duplicates", 0),
			errores_guardado=errores_guardado,
			reparados=reparados,
			rechazados=rechazados,
			incidencias=incidencias,
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
			incidencias=[],
		)