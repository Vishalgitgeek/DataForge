from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app
from app.infrastructure import database

client = TestClient(app)


def test_liveness_returns_ok() -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_readiness_exposes_dependency_check_shape(monkeypatch) -> None:
    async def available_database() -> None:
        return None

    monkeypatch.setattr(database, "check_database", available_database)
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "application": {
                "status": "ready",
                "detail": "DataForge API configuration loaded",
            },
            "database": {
                "status": "ready",
                "detail": "database connectivity check succeeded",
            },
        },
    }


def test_client_request_id_is_preserved() -> None:
    response = client.get(
        "/api/v1/health/live",
        headers={"X-Request-ID": "test-request-123"},
    )

    assert response.headers["X-Request-ID"] == "test-request-123"


def test_readiness_reports_database_failure(monkeypatch) -> None:
    async def unavailable_database() -> None:
        raise OperationalError("SELECT 1", {}, ConnectionError("unavailable"))

    monkeypatch.setattr(database, "check_database", unavailable_database)
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "application": {
                "status": "ready",
                "detail": "DataForge API configuration loaded",
            },
            "database": {
                "status": "failed",
                "detail": "database connectivity check failed",
            },
        },
    }


def test_liveness_does_not_require_database(monkeypatch) -> None:
    async def unavailable_database() -> None:
        raise OperationalError("SELECT 1", {}, ConnectionError("unavailable"))

    monkeypatch.setattr(database, "check_database", unavailable_database)
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
