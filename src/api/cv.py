from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from src.api.wrappers.api_cv import router as wrapper_cv_router

app = FastAPI(
    title="IEI ITV API",
    description="API del wrapper de Comunidad Valenciana",
    version="1.0.0"
)

app.include_router(wrapper_cv_router)

@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")