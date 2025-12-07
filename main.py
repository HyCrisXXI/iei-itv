# main.py
from src.database.session import create_db_and_tables
from src.api.main import app

def startup():
    """Función que se ejecuta al iniciar la aplicación."""
    print("Iniciando aplicación...")
    print("Creando tablas en la base de datos si no existen...")
    create_db_and_tables()
    print("Tablas creadas.")

if __name__ == "__main__":
    startup()