from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes import auth
from app.infrastructure import database
from app.main import app
from app.models import User


def test_register_route_returns_safe_user_response_and_uses_transaction_middleware(
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email="user@example.com",
        password_hash="$argon2id$v=19$m=1,t=1,p=1$not-a-password",
        created_at=now,
        updated_at=now,
    )
    sessions = []

    class FakeSession:
        async def commit(self) -> None:
            self.committed = True

        async def rollback(self) -> None:
            self.rolled_back = True

        async def close(self) -> None:
            self.closed = True

    def create_session() -> FakeSession:
        session = FakeSession()
        session.committed = False
        session.rolled_back = False
        session.closed = False
        sessions.append(session)
        return session

    async def service_stub(*_args) -> User:
        return user

    monkeypatch.setattr(database, "session_factory", create_session)
    monkeypatch.setattr(auth, "register_user", service_stub)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com", "password": "a" * 12},
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(user.id),
        "email": "user@example.com",
        "created_at": now.isoformat().replace("+00:00", "Z"),
    }
    assert "password" not in response.json()
    assert "password_hash" not in response.json()
    assert sessions[0].committed is True
    assert sessions[0].rolled_back is False
    assert sessions[0].closed is True
