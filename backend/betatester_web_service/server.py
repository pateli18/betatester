import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from betatester_web_service.db.base import create_tables, shutdown_session
from betatester_web_service.routes import config, data, scraper
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
    await create_tables()
    yield
    await shutdown_session()
    await model_client.aclose()


app = FastAPI(lifespan=lifespan, title="BetaTester", version="0.0.0")
app.include_router(scraper.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(data.router)


origins = [
    "https://trace.playwright.dev",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


if settings.environment != Environment.dev:

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse("./betatester_web_service/ui/index.html")

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok"}

    app.mount(
        "/", StaticFiles(directory="./betatester_web_service/ui/"), name="ui"
    )
