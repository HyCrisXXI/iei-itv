# src/database/models.py
from sqlalchemy import Column, Integer, String, Float, Enum, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy_utils import ChoiceType
import enum

Base = declarative_base()

class TipoEstacion(enum.Enum):
    Estacion_fija = "Fija"
    Estacion_movil = "Movil"
    Otros = "Otros"


class Provincia(Base):
    __tablename__ = 'provincias'

    codigo = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)

    # Relación con Localidades (1 Provincia tiene 1 o más Localidades)
    localidades = relationship("Localidad", back_populates="provincia", lazy="joined")

    def __repr__(self):
        return f"<Provincia(codigo='{self.codigo}', nombre='{self.nombre}')>"



class Localidad(Base):
    __tablename__ = 'localidades'

    codigo = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String, nullable=False)

    # Relación con Provincia (N localidades a 1 Provincia)
    codigo_provincia = Column(Integer, ForeignKey('provincias.codigo'), nullable=False)
    provincia = relationship("Provincia", back_populates="localidades", lazy="joined")

    # Relación con Estaciones (1 Localidad tiene 0 o más Estaciones)
    estaciones = relationship("Estacion", back_populates="localidad", lazy="joined")

    def __repr__(self):
        return f"<Localidad(codigo='{self.codigo}', nombre='{self.nombre}', provincia='{self.codigo_provincia}')>"



class Estacion(Base):
    __tablename__ = 'estaciones'
    cod_estacion = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String, nullable=False)
    tipo = Column(ChoiceType(TipoEstacion, impl=String()), nullable=False)
    direccion = Column(String)
    codigo_postal = Column(String)
    latitud = Column(Float)
    longitud = Column(Float)
    descripcion = Column(String)
    horario = Column(String)
    contacto = Column(String)
    url = Column(String)

    # Relación con Localidad (N Estaciones a 1 Localidad)
    codigo_localidad = Column(Integer, ForeignKey('localidades.codigo'), nullable=True)
    localidad = relationship("Localidad", back_populates="estaciones", lazy="joined")

    # Origen de datos (ej. 'gal', 'cat', 'cv') para saber de dónde vino el registro
    origen_datos = Column(String(3), nullable=False)

    def __repr__(self):
        return (f"<Estacion(cod_estacion='{self.cod_estacion}', nombre='{self.nombre}', "
                f"tipo='{self.tipo.value}', localidad='{self.codigo_localidad}')>")