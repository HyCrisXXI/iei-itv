# core/models.py
from sqlalchemy import Column, Integer, String, Float, Enum, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy_utils import ChoiceType
import enum

Base = declarative_base()

class TipoEstacion(enum.Enum):
    Estacion_fija = "Estación fija"
    Estacion_movil = "Estación móvil"
    Otros = "Otros"

class Provincia(Base):
    __tablename__ = 'provincias'

    codigo = Column(String, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    
    # Relación con Localidades (1 Provincia tiene 1 o más Localidades)
    # lazy='joined' cargará las localidades junto con la provincia
    localidades = relationship("Localidad", back_populates="provincia", lazy="joined")

    def __repr__(self):
        return f"<Provincia(codigo='{self.codigo}', nombre='{self.nombre}')>"

class Localidad(Base):
    __tablename__ = 'localidades'

    codigo = Column(String, primary_key=True, index=True)
    nombre = Column(String, nullable=False)

    # Relación con Provincia (N localidades a 1 Provincia)
    # 'codigo_provincia' es la clave foránea
    codigo_provincia = Column(String, ForeignKey('provincias.codigo'), nullable=False)
    provincia = relationship("Provincia", back_populates="localidades", lazy="joined")
    
    # Relación con Estaciones (1 Localidad tiene 0 o más Estaciones)
    estaciones = relationship("Estacion", back_populates="localidad", lazy="joined")

    def __repr__(self):
        return f"<Localidad(codigo='{self.codigo}', nombre='{self.nombre}', provincia='{self.codigo_provincia}')>"

class Estacion(Base):
    __tablename__ = 'estaciones'

    cod_estacion = Column(String, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    tipo = Column(ChoiceType(TipoEstacion, impl=String()), nullable=False)
    direccion = Column(String)
    codigo_postal = Column(String(5))
    longitud = Column(Float)
    latitud = Column(Float)
    descripcion = Column(String)
    horario = Column(String)
    contacto = Column(String)
    url = Column(String)

    # Relación con Localidad (N Estaciones a 1 Localidad)
    # 'codigo_localidad' es la clave foránea
    codigo_localidad = Column(String, ForeignKey('localidades.codigo'), nullable=False)
    localidad = relationship("Localidad", back_populates="estaciones", lazy="joined")
    
    # Origen de datos (ej. 'GAL', 'CAT', 'CV') para saber de dónde vino el registro
    origen_datos = Column(String(3), nullable=False)

    def __repr__(self):
        return (f"<Estacion(cod_estacion='{self.cod_estacion}', nombre='{self.nombre}', "
                f"tipo='{self.tipo.value}', localidad='{self.codigo_localidad}')>")