from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_authenticated_user_id
from app.api.exception_handlers import authentication_exception_handler
from app.core import jwt as jwt_utility
from app.core.config import Settings
from app.core.errors import AuthenticationError

SECRET = "test-secret-that-is-at-least-32-characters"
OTHER_SECRET = "different-test-secret-that-is-32-characters"


def make_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_exception_handler(
        AuthenticationError,
        authentication_exception_handler,
    )

    @test_app.get("/protected")
    def protected(user_id: UUID = Depends(get_authenticated_user_id)):
        return {"user_id": str(user_id)}

    return test_app


def make_token(
    *,
    secret: str = SECRET,
    **claims: object,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "type": "access",
        "iss": "dataforge-api",
        "aud": "dataforge-api",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def jwt_settings(monkeypatch):
    settings = Settings(jwt_secret=SECRET)
    monkeypatch.setattr(jwt_utility, "get_settings", lambda: settings)
    return settings


@pytest.mark.usefixtures("jwt_settings")
def test_authenticated_user_dependency_accepts_valid_access_token() -> None:
    user_id = uuid4()
    token = jwt_utility.create_access_token(user_id)

    with TestClient(make_test_app()) as client:
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {"user_id": str(user_id)}


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("missing", "authentication_required"),
        ("wrong_scheme", "authentication_required"),
        ("malformed", "authentication_required"),
        ("expired", "token_expired"),
        ("wrong_issuer", "authentication_required"),
        ("wrong_audience", "authentication_required"),
        ("wrong_type", "authentication_required"),
        ("invalid_subject", "authentication_required"),
        ("invalid_signature", "authentication_required"),
    ],
)
@pytest.mark.usefixtures("jwt_settings")
def test_authentication_dependency_returns_standard_error_envelope(
    case: str,
    expected_code: str,
) -> None:
    now = datetime.now(UTC)
    headers = {}
    if case == "wrong_scheme":
        headers["Authorization"] = "Basic credentials"
    elif case == "malformed":
        headers["Authorization"] = "Bearer not-a-jwt"
    elif case == "expired":
        token = make_token(
            exp=now - timedelta(minutes=1),
            iat=now - timedelta(minutes=16),
        )
        headers["Authorization"] = f"Bearer {token}"
    elif case == "wrong_issuer":
        token = make_token(iss="wrong-issuer")
        headers["Authorization"] = f"Bearer {token}"
    elif case == "wrong_audience":
        token = make_token(aud="wrong-audience")
        headers["Authorization"] = f"Bearer {token}"
    elif case == "wrong_type":
        token = make_token(type="refresh")
        headers["Authorization"] = f"Bearer {token}"
    elif case == "invalid_subject":
        token = make_token(sub="not-a-uuid")
        headers["Authorization"] = f"Bearer {token}"
    elif case == "invalid_signature":
        token = make_token(secret=OTHER_SECRET)
        headers["Authorization"] = f"Bearer {token}"

    with TestClient(make_test_app()) as client:
        response = client.get("/protected", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == expected_code
    assert response.json()["error"]["retryable"] is False
    assert isinstance(response.json()["error"]["message"], str)
    assert "request_id" in response.json()
