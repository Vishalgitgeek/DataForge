from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.infrastructure import database

router = APIRouter(tags=["Health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]


class ReadinessCheck(BaseModel):
    status: Literal["ready", "not_configured", "failed"]
    detail: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, ReadinessCheck]


@router.get("/health/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(response: Response) -> ReadinessResponse:
    settings = get_settings()
    checks = {
        "application": ReadinessCheck(
            status="ready",
            detail=f"{settings.app_name} configuration loaded",
        ),
    }
    try:
        await database.check_database()
    except (OSError, SQLAlchemyError, TimeoutError):
        response.status_code = 503
        checks["database"] = ReadinessCheck(
            status="failed",
            detail="database connectivity check failed",
        )
        return ReadinessResponse(status="not_ready", checks=checks)

    checks["database"] = ReadinessCheck(
        status="ready",
        detail="database connectivity check succeeded",
    )
    return ReadinessResponse(status="ready", checks=checks)
