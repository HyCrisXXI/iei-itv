# src/database/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .settings import DATABASE_URL
from .models import Base

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crea las tablas si no existen, sino las ignora
def create_db_and_tables():
    """
    Crea en la base de datos todas las tablas definidas en models.py.
    Además, habilita Row Level Security (RLS) en cada tabla para Supabase.
    """
    Base.metadata.create_all(bind=engine)

    # Habilita RLS en cada tabla 
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE provincias ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text("ALTER TABLE localidades ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text("ALTER TABLE estaciones ENABLE ROW LEVEL SECURITY;"))
        conn.commit()

# Obtener sesión de la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()