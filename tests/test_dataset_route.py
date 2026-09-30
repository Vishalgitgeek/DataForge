from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import dependencies
from app.api.routes import datasets
from app.schemas.dataset import DatasetPage, PageInfo
from app.infrastructure import database
from app.main import app
from app.models import Dataset, DatasetVersion, DatasetVersionStatus
from app.schemas.dataset import CreateDatasetRequest, CreateVersionRequest


def test_create_dataset_route_calls_service_and_returns_response(monkeypatch) -> None:
    owner_id = uuid4()
    now = datetime.now(UTC)
    dataset = Dataset(
        id=uuid4(),
        owner_id=owner_id,
        name="Quarterly sales",
        description="Sales by region",
        created_at=now,
        updated_at=now,
    )
    sessions = []

    class FakeSession:
        committed = False
        closed = False
        rollback_count = 0

        async def commit(self) -> None:
            self.committed = True

        async def rollback(self) -> None:
            self.rollback_count += 1

        async def close(self) -> None:
            self.closed = True

    def create_session() -> FakeSession:
        session = FakeSession()
        sessions.append(session)
        return session

    service_calls: list[tuple[object, object, CreateDatasetRequest]] = []

    async def authenticated_owner() -> UUID:
        return owner_id

    async def service_stub(
        passed_session: object,
        passed_owner_id: UUID,
        request: CreateDatasetRequest,
    ) -> Dataset:
        service_calls.append((passed_session, passed_owner_id, request))
        return dataset

    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_authenticated_user_id,
        authenticated_owner,
    )
    monkeypatch.setattr(database, "session_factory", create_session)
    monkeypatch.setattr(datasets, "create_dataset", service_stub)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/datasets",
            json={
                "name": "Quarterly sales",
                "description": "Sales by region",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(dataset.id)
    assert body["name"] == "Quarterly sales"
    assert body["description"] == "Sales by region"
    assert datetime.fromisoformat(body["created_at"].replace("Z", "+00:00")) == now
    assert datetime.fromisoformat(body["updated_at"].replace("Z", "+00:00")) == now
    assert len(service_calls) == 1
    called_session, called_owner_id, called_request = service_calls[0]
    assert len(sessions) == 1
    assert called_session is sessions[0]
    assert called_owner_id == owner_id
    assert called_request == CreateDatasetRequest(
        name="Quarterly sales",
        description="Sales by region",
    )
    assert sessions[0].committed is True
    assert sessions[0].rollback_count == 0
    assert sessions[0].closed is True


def test_get_dataset_route_scopes_with_authenticated_user_and_returns_response(
    monkeypatch,
) -> None:
    owner_id = uuid4()
    dataset_id = uuid4()
    now = datetime.now(UTC)
    dataset = Dataset(
        id=dataset_id,
        owner_id=owner_id,
        name="Quarterly sales",
        description="Sales by region",
        created_at=now,
        updated_at=now,
    )
    calls = []

    class FakeSession:
        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    async def get_authenticated_user() -> UUID:
        return owner_id

    async def service_stub(session, passed_dataset_id, passed_owner_id):
        calls.append((session, passed_dataset_id, passed_owner_id))
        return dataset

    monkeypatch.setattr(database, "session_factory", FakeSession)
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_authenticated_user_id,
        get_authenticated_user,
    )
    monkeypatch.setattr(datasets, "get_dataset", service_stub)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/datasets/{dataset_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(dataset_id)
    assert body["name"] == "Quarterly sales"
    assert body["description"] == "Sales by region"
    assert datetime.fromisoformat(body["created_at"].replace("Z", "+00:00")) == now
    assert datetime.fromisoformat(body["updated_at"].replace("Z", "+00:00")) == now
    assert calls[0][1:] == (dataset_id, owner_id)


def test_get_dataset_route_rejects_unauthenticated_request(monkeypatch) -> None:
    class FakeSession:
        async def commit(self) -> None:
            raise AssertionError("authentication errors must not commit")

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    monkeypatch.setattr(database, "session_factory", FakeSession)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/datasets/{uuid4()}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_delete_dataset_route_uses_authenticated_owner_and_returns_empty_204(
    monkeypatch,
) -> None:
    dataset_id = uuid4()
    owner_id = uuid4()
    calls = []

    class FakeSession:
        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    async def authenticated_user() -> UUID:
        return owner_id

    async def service_stub(session, passed_dataset_id, passed_owner_id):
        calls.append((session, passed_dataset_id, passed_owner_id))

    monkeypatch.setattr(database, "session_factory", FakeSession)
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_authenticated_user_id,
        authenticated_user,
    )
    monkeypatch.setattr(datasets, "soft_delete_dataset", service_stub)

    with TestClient(app) as client:
        response = client.delete(f"/api/v1/datasets/{dataset_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert calls[0][1:] == (dataset_id, owner_id)


def test_delete_dataset_route_rejects_unauthenticated_request(monkeypatch) -> None:
    class FakeSession:
        async def commit(self) -> None:
            raise AssertionError("authentication errors must not commit")

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    monkeypatch.setattr(database, "session_factory", FakeSession)

    with TestClient(app) as client:
        response = client.delete(f"/api/v1/datasets/{uuid4()}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_create_dataset_version_route_returns_created_version(monkeypatch) -> None:
    dataset_id = uuid4()
    owner_id = uuid4()
    now = datetime.now(UTC)
    version = DatasetVersion(
        id=uuid4(),
        dataset_id=dataset_id,
        version_number=1,
        status=DatasetVersionStatus.CREATED,
        created_at=now,
        updated_at=now,
    )
    calls = []

    class FakeSession:
        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    async def authenticated_user() -> UUID:
        return owner_id

    async def service_stub(session, passed_dataset_id, passed_owner_id, request):
        calls.append((session, passed_dataset_id, passed_owner_id, request))
        return version

    monkeypatch.setattr(database, "session_factory", FakeSession)
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_authenticated_user_id,
        authenticated_user,
    )
    monkeypatch.setattr(datasets, "create_dataset_version", service_stub)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/datasets/{dataset_id}/versions",
            json={
                "filename": "sales.csv",
                "content_type": "text/csv",
                "byte_size": 42,
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(version.id),
        "dataset_id": str(dataset_id),
        "version_number": 1,
        "status": "CREATED",
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "updated_at": now.isoformat().replace("+00:00", "Z"),
    }
    assert calls[0][1:] == (
        dataset_id,
        owner_id,
        CreateVersionRequest(
            filename="sales.csv",
            content_type="text/csv",
            byte_size=42,
        ),
    )


@pytest.mark.parametrize(
    "body",
    [
        {"filename": "", "content_type": "text/csv", "byte_size": 1},
        {"filename": "x" * 256, "content_type": "text/csv", "byte_size": 1},
        {"filename": "sales.csv", "content_type": "application/json", "byte_size": 1},
        {"filename": "sales.csv", "content_type": "text/csv", "byte_size": 0},
    ],
)
def test_create_dataset_version_route_returns_validation_envelope_for_invalid_request(
    monkeypatch,
    body: dict[str, object],
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
        dependencies.get_authenticated_user_id,
        lambda: uuid4(),
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/datasets/{uuid4()}/versions",
            json=body,
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_dataset_version_route_rejects_unauthenticated_request(
    monkeypatch,
) -> None:
    class FakeSession:
        async def commit(self) -> None:
            raise AssertionError("authentication errors must not commit")

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    monkeypatch.setattr(database, "session_factory", FakeSession)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/datasets/{uuid4()}/versions",
            json={
                "filename": "sales.csv",
                "content_type": "text/csv",
                "byte_size": 42,
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_list_datasets_route_uses_default_page_size_and_authenticated_owner(
    monkeypatch,
) -> None:
    owner_id = uuid4()
    calls = []

    class FakeSession:
        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    async def authenticated_user() -> UUID:
        return owner_id

    async def service_stub(session, passed_owner_id, page_size, cursor):
        calls.append((session, passed_owner_id, page_size, cursor))
        return DatasetPage(items=[], page_info=PageInfo(has_more=False))

    monkeypatch.setattr(database, "session_factory", FakeSession)
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_authenticated_user_id,
        authenticated_user,
    )
    monkeypatch.setattr(datasets, "list_datasets", service_stub)

    with TestClient(app) as client:
        response = client.get("/api/v1/datasets")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page_info": {"next_cursor": None, "has_more": False},
    }
    assert calls[0][1:] == (owner_id, 20, None)


@pytest.mark.parametrize("page_size", [1, 100])
def test_list_datasets_route_accepts_page_size_bounds(
    monkeypatch,
    page_size: int,
) -> None:
    class FakeSession:
        async def commit(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    async def service_stub(*_args):
        return DatasetPage(items=[], page_info=PageInfo(has_more=False))

    monkeypatch.setattr(database, "session_factory", FakeSession)
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_authenticated_user_id,
        lambda: uuid4(),
    )
    monkeypatch.setattr(datasets, "list_datasets", service_stub)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/datasets?page_size={page_size}")

    assert response.status_code == 200


@pytest.mark.parametrize("page_size", [0, 101])
def test_list_datasets_route_rejects_page_size_outside_bounds(
    monkeypatch,
    page_size: int,
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
        dependencies.get_authenticated_user_id,
        lambda: uuid4(),
    )

    with TestClient(app) as client:
        response = client.get(f"/api/v1/datasets?page_size={page_size}")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_datasets_route_rejects_invalid_cursor_with_validation_envelope(
    monkeypatch,
) -> None:
    class FakeSession:
        async def commit(self) -> None:
            raise AssertionError("validation errors must not commit")

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    monkeypatch.setattr(database, "session_factory", FakeSession)
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_authenticated_user_id,
        lambda: uuid4(),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/datasets?cursor=not-a-valid-cursor")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["retryable"] is False


def test_list_datasets_route_rejects_unauthenticated_request(monkeypatch) -> None:
    class FakeSession:
        async def commit(self) -> None:
            raise AssertionError("authentication errors must not commit")

        async def rollback(self) -> None:
            pass

        async def close(self) -> None:
            pass

    monkeypatch.setattr(database, "session_factory", FakeSession)

    with TestClient(app) as client:
        response = client.get("/api/v1/datasets")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
