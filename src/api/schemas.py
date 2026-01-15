# src/api/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class TipoEstacionSchema(str, Enum):
    fija = "Fija"
    movil = "Movil"
    otros = "Otros"


class ProvinciaSchema(BaseModel):
    codigo: int = Field(..., description="Código único de la provincia")
    nombre: str = Field(..., description="Nombre de la provincia")

    class Config:
        from_attributes = True


class LocalidadSchema(BaseModel):
    codigo: int = Field(..., description="Código único de la localidad")
    nombre: str = Field(..., description="Nombre de la localidad")
    codigo_provincia: int = Field(..., description="Código de la provincia asociada")

    class Config:
        from_attributes = True


class EstacionSchema(BaseModel):
    cod_estacion: int = Field(..., description="Código único de la estación")
    nombre: str = Field(..., description="Nombre de la estación ITV")
    tipo: str = Field(..., description="Tipo de estación: Fija, Movil, u Otros")
    direccion: Optional[str] = Field(None, description="Dirección física de la estación")
    codigo_postal: Optional[str] = Field(None, description="Código postal")
    latitud: Optional[float] = Field(None, description="Coordenada de latitud")
    longitud: Optional[float] = Field(None, description="Coordenada de longitud")
    descripcion: Optional[str] = Field(None, description="Descripción adicional")
    horario: Optional[str] = Field(None, description="Horario de atención")
    contacto: Optional[str] = Field(None, description="Información de contacto")
    url: Optional[str] = Field(None, description="URL del sitio web")
    codigo_localidad: Optional[int] = Field(None, description="Código de la localidad")
    origen_datos: str = Field(..., description="Origen de los datos (gal, cat, cv)")
    
    localidad_nombre: Optional[str] = Field(None, description="Nombre de la localidad")
    provincia_nombre: Optional[str] = Field(None, description="Nombre de la provincia")

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    total: int = Field(..., description="Número total de resultados encontrados")
    resultados: List[EstacionSchema] = Field(..., description="Lista de estaciones encontradas")


class RegistroReparadoSchema(BaseModel):
    fuente: str = Field(..., description="Identificador de la comunidad")
    nombre: str = Field(..., description="Nombre del registro afectado")
    localidad: Optional[str] = Field(None, description="Localidad asociada")
    motivo: str = Field(..., description="Motivo del error detectado")
    operacion: str = Field(..., description="Operación correctiva aplicada")


class RegistroRechazadoSchema(BaseModel):
    fuente: str = Field(..., description="Identificador de la comunidad")
    nombre: str = Field(..., description="Nombre del registro descartado")
    localidad: Optional[str] = Field(None, description="Localidad asociada")
    motivo: str = Field(..., description="Motivo del rechazo")


class LoadRequest(BaseModel):
    fuentes: List[str] = Field(
        ...,
        description="Listado de comunidades a cargar (gal, cv, cat)",
        min_length=1,
        examples=[["gal", "cv"]],
    )


class FuenteCargaDetalle(BaseModel):
    fuente: str = Field(..., description="Identificador de la comunidad procesada")
    registros_origen: int = Field(..., description="Total de registros obtenidos del origen")
    registros_transformados: int = Field(..., description="Registros válidos tras la transformación")
    rechazados_transformacion: int = Field(..., description="Registros descartados durante la transformación")
    insertados: int = Field(..., description="Registros nuevos insertados en base de datos")
    duplicados: int = Field(..., description="Registros detectados como duplicados")
    errores_guardado: List[str] = Field(default_factory=list, description="Errores detectados al guardar")
    reparados: List[RegistroReparadoSchema] = Field(
        default_factory=list,
        description="Registros corregidos durante la transformación",
    )
    rechazados: List[RegistroRechazadoSchema] = Field(
        default_factory=list,
        description="Registros descartados durante la transformación",
    )


class LoadProcessResponse(BaseModel):
    total_fuentes: int = Field(..., description="Número de comunidades procesadas")
    total_insertados: int = Field(..., description="Total de registros insertados")
    total_duplicados: int = Field(..., description="Total de registros duplicados")
    total_rechazados: int = Field(..., description="Total de registros descartados (transformación + guardado)")
    detalles: List[FuenteCargaDetalle] = Field(..., description="Detalle por comunidad procesada")
    reparados: List[RegistroReparadoSchema] = Field(
        default_factory=list,
        description="Listado consolidado de registros corregidos",
    )
    rechazados: List[RegistroRechazadoSchema] = Field(
        default_factory=list,
        description="Listado consolidado de registros descartados",
    )
