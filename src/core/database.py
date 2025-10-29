# src/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config.settings import DATABASE_URL
from src.core.models import Base

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crea las tablas si no existen, sino las ignora
def create_db_and_tables():
    """
    Crea en la base de datos todas las tablas definidas en models.py.
    """
    Base.metadata.create_all(bind=engine)

# Obtener sesión de la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()