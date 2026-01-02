from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from src.api.routes.search import router as search_router
from src.api.wrappers.api_cat import router as wrapper_cat_router
from src.api.wrappers.api_cv import router as wrapper_cv_router
from src.api.wrappers.api_gal import router as wrapper_gal_router

app = FastAPI(
    title="IEI ITV API",
    description="API para la gestión y búsqueda de estaciones ITV en España",
    version="1.0.0"
)

# Incluye los routers disponibles
app.include_router(search_router)
app.include_router(wrapper_cat_router)
app.include_router(wrapper_cv_router)
app.include_router(wrapper_gal_router)

@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")

# Los datos regionales se exponen a través de los routers de wrappers