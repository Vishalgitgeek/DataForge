from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, request_logging_middleware
from app.infrastructure.database import dispose_database

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await dispose_database()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend API for the DataForge data analysis platform.",
    lifespan=lifespan,
)
app.middleware("http")(request_logging_middleware)
app.include_router(api_router, prefix="/api/v1")
