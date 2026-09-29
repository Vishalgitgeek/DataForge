from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api import dependencies
from app.api.routes import datasets
from app.infrastructure import database
from app.main import app
from app.models import Dataset
from app.schemas.dataset import CreateDatasetRequest


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
        dependencies.get_authenticated_owner_id,
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
