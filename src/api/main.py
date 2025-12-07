from fastapi import FastAPI
from src.wrappers.wrapper_gal import csvtojson

app = FastAPI()

@app.get("/gal")
def get_gal():
    """Devuelve los datos de Galicia en formato JSON."""
    return csvtojson()

@app.get("/cat")
def get_cat():
    """Devuelve los datos de Cataluña en formato JSON."""
    return csvtojson()

@app.get("/cv")
def get_cv():
    """Devuelve los datos de Comunidad Valenciana en formato JSON."""
    return csvtojson()