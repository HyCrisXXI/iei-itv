# main.py
from src.database.session import create_db_and_tables
from src.extractors.extractor_gal import  transformed_data_to_database as gal_to_db
from src.extractors.extractor_cat import  transformed_data_to_database as cat_to_db


def startup():
    """Función que se ejecuta al iniciar la aplicación."""
    print("Iniciando aplicación...")
    print("Creando tablas en la base de datos si no existen...")
    create_db_and_tables()
    print("Subiendo datos de Extacions_ITV.csv a la BD.")
    gal_to_db()
    print("Subiendo datos de ITV-CAT.xml a la BD.")
    cat_to_db()

if __name__ == "__main__":
    startup()