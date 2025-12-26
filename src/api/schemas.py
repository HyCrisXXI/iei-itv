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
