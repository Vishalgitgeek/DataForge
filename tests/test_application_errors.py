from app.core.errors import DatasetNameConflictError
from fastapi.testclient import TestClient

from app.api import dependencies
from app.api.routes import datasets
from app.infrastructure import database
from app.main import app

def test_dataset_name_conflict_error_carries_api_conflict_metadata() -> None:
    error = DatasetNameConflictError()

    assert error.status_code == 409
    assert error.code == "conflict"
    assert error.retryable is False
    assert error.message == "An active dataset with this name already exists."
    assert str(error) == error.message


def test_dataset_name_conflict_handler_returns_documented_error_envelope(
    monkeypatch,
) -> None:
    class FakeSession:
        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    monkeypatch.setattr(database, "session_factory", FakeSession)
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_authenticated_owner_id,
        lambda: "f1a7ef14-7a92-4705-9971-33060da8ba3b",
    )

    async def raise_dataset_conflict(*_args, **_kwargs):
        raise DatasetNameConflictError()

    monkeypatch.setattr(datasets, "create_dataset", raise_dataset_conflict)
    request_id = "dataset-conflict-test-request"

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/datasets",
            headers={"X-Request-ID": request_id},
            json={"name": "Quarterly sales"},
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conflict",
            "message": "An active dataset with this name already exists.",
            "retryable": False,
        },
        "request_id": request_id,
    }
    assert response.headers["X-Request-ID"] == request_id
