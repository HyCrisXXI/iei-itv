from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from src.api.routes.load import router as load_router

app = FastAPI(
    title="IEI ITV API",
    description="API para carga de estaciones",
    version="1.0.1"
)

app.include_router(load_router)

@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")