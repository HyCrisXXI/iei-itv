# main.py
from src.core.database import create_db_and_tables


def startup():
    """Función que se ejecuta al iniciar la aplicación."""
    print("Iniciando aplicación...")
    print("Creando tablas en la base de datos si no existen...")
    create_db_and_tables()
    print("Tablas verificadas/creadas con éxito.")

if __name__ == "__main__":
    startup()