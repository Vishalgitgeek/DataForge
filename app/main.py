from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.exception_handlers import dataset_name_conflict_exception_handler
from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import DatasetNameConflictError
from app.core.logging import configure_logging, request_logging_middleware
from app.infrastructure.database import dispose_database
from app.infrastructure.transaction import transaction_middleware

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
app.add_exception_handler(
    DatasetNameConflictError,
    dataset_name_conflict_exception_handler,
)
app.middleware("http")(request_logging_middleware)
app.middleware("http")(transaction_middleware)
app.include_router(api_router, prefix="/api/v1")
