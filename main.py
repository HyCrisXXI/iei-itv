# main.py
from src.database.session import create_db_and_tables
from src.extractors.extractor_gal import  transformed_data_to_database as gal_to_db
from src.extractors.extractor_cat import  transformed_data_to_database as cat_to_db
from src.extractors.extractor_cv import insert_transformed_to_db as cv_to_db
from src.extractors.extractor_cv import jsontojson, transform_cv_record, scrape_sitval_centros


def startup():
    """Función que se ejecuta al iniciar la aplicación."""
    print("Iniciando aplicación...")
    print("Creando tablas en la base de datos si no existen...")
    create_db_and_tables()
    print("Subiendo datos de Extacions_ITV.csv a la BD.")
    gal_to_db()
    print("Subiendo datos de ITV-CAT.xml a la BD.")
    cat_to_db()
    print("Subiendo datos de estaciones SITVAL a la BD.")
    cv_raw = jsontojson()
    municipios, codigos_postales, provincias = scrape_sitval_centros()
    station_names_map = dict(zip(codigos_postales, municipios))
    cv_transformed = [transform_cv_record(record, station_names_map) for record in cv_raw]
    cv_transformed = [t for t in cv_transformed if t is not None]
    cv_to_db(cv_transformed)

if __name__ == "__main__":
    startup()