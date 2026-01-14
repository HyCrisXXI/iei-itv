from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from src.api.routes.search import router as search_router

app = FastAPI(
    title="IEI ITV API",
    description="API para búsqueda de estaciones ITV en España",
    version="1.0.1"
)

app.include_router(search_router)

@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")
