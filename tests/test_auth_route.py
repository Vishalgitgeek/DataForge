from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes import auth
from app.core.errors import RefreshTokenReuseError
from app.infrastructure import database
from app.main import app
from app.models import User
from app.schemas.auth import AccessTokenResponse, AuthResponse


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


def test_login_route_returns_access_token_response_and_commits(monkeypatch) -> None:
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

    async def service_stub(*_args) -> AccessTokenResponse:
        return AccessTokenResponse(
            access_token="encoded-token",
            token_type="bearer",
            expires_in=900,
        )

    monkeypatch.setattr(database, "session_factory", create_session)
    monkeypatch.setattr(auth, "login_user", service_stub)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "  User@Example.COM  ", "password": "password"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "encoded-token",
        "token_type": "bearer",
        "expires_in": 900,
    }
    assert "refresh_token" not in response.json()
    assert sessions[0].committed is True
    assert sessions[0].rolled_back is False
    assert sessions[0].closed is True


def test_login_route_returns_generic_invalid_credentials_error(monkeypatch) -> None:
    class FakeSession:
        async def commit(self) -> None:
            raise AssertionError("invalid credentials must not commit")

        async def rollback(self) -> None:
            self.rolled_back = True

        async def close(self) -> None:
            pass

    async def service_stub(*_args):
        from app.core.errors import InvalidCredentialsError

        raise InvalidCredentialsError()

    monkeypatch.setattr(database, "session_factory", FakeSession)
    monkeypatch.setattr(auth, "login_user", service_stub)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={"X-Request-ID": "login-error-request"},
            json={"email": "unknown@example.com", "password": "password"},
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "invalid_credentials",
            "message": "Invalid email or password.",
            "retryable": False,
        },
        "request_id": "login-error-request",
    }


def test_refresh_route_returns_auth_response(monkeypatch) -> None:
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

    async def service_stub(_session, raw_token: str) -> AuthResponse:
        assert raw_token == "presented-refresh-token"
        return AuthResponse(
            access_token="new-access-token",
            refresh_token="replacement-refresh-token",
            token_type="bearer",
            expires_in=900,
        )

    monkeypatch.setattr(database, "session_factory", create_session)
    monkeypatch.setattr(auth, "rotate_refresh_token", service_stub)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "presented-refresh-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "new-access-token",
        "refresh_token": "replacement-refresh-token",
        "token_type": "bearer",
        "expires_in": 900,
    }
    assert sessions[0].committed is True
    assert sessions[0].rolled_back is False
    assert sessions[0].closed is True


def test_refresh_reuse_returns_standard_401_and_commits_marked_transaction(
    monkeypatch,
) -> None:
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

    async def service_stub(*_args):
        raise RefreshTokenReuseError()

    monkeypatch.setattr(database, "session_factory", create_session)
    monkeypatch.setattr(auth, "rotate_refresh_token", service_stub)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "reused-token"},
        )

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "authentication_required",
        "message": "Authentication is required.",
        "retryable": False,
    }
    assert sessions[0].committed is True
    assert sessions[0].rolled_back is False
    assert sessions[0].closed is True


def test_logout_returns_empty_204_and_uses_normal_transaction_commit(
    monkeypatch,
) -> None:
    sessions = []
    revoked_tokens: list[str] = []

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

    async def service_stub(_session, raw_token: str) -> None:
        revoked_tokens.append(raw_token)

    monkeypatch.setattr(database, "session_factory", create_session)
    monkeypatch.setattr(auth, "revoke_refresh_token", service_stub)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "presented-refresh-token"},
        )

    assert response.status_code == 204
    assert response.content == b""
    assert revoked_tokens == ["presented-refresh-token"]
    assert sessions[0].committed is True
    assert sessions[0].rolled_back is False
    assert sessions[0].closed is True
