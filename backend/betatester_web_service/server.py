import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from betatester_web_service.routes import data, scraper
from betatester_web_service.utils import (
    Environment,
    model_client,
    settings,
    setup_logging,
)

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await model_client.aclose()


app = FastAPI(lifespan=lifespan, title="Betateser", version="0.0.0")
app.include_router(scraper.router, prefix="/api/v1")
app.include_router(data.router)


if settings.environment != Environment.dev:

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse("./betatester/ui/index.html")

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok"}

    app.mount("/", StaticFiles(directory="./betatester/ui/"), name="ui")
