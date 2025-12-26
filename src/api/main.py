from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from src.wrappers.wrapper_gal import csvtojson
from src.wrappers.wrapper_cat import xmltojson
from src.wrappers.wrapper_cv import jsontojson
from src.api.routes.search import router as search_router

app = FastAPI(
    title="IEI ITV API",
    description="API para la gestión y búsqueda de estaciones ITV en España",
    version="1.0.0"
)

# Incluye el router de búsqueda
app.include_router(search_router)

@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")

# Endpoints para obtener datos de las estaciones
@app.get("/gal")
def get_gal():
    """Devuelve los datos de Galicia en formato JSON."""
    return csvtojson()

@app.get("/cat")
def get_cat():
    """Devuelve los datos de Cataluña en formato JSON."""
    return xmltojson()

@app.get("/cv")
def get_cv():
    """Devuelve los datos de Comunidad Valenciana en formato JSON."""
    return jsontojson()