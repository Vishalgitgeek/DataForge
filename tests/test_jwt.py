from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.core import jwt as jwt_utility
from app.core.config import Settings


def test_create_access_token_contains_configured_claims(monkeypatch) -> None:
    secret = "test-secret-that-is-at-least-32-characters"
    settings = Settings(jwt_secret=secret)
    monkeypatch.setattr(jwt_utility, "get_settings", lambda: settings)
    user_id = uuid4()
    issued_at = datetime.now(UTC)

    token = jwt_utility.create_access_token(user_id, now=issued_at)
    claims = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        issuer="dataforge-api",
        audience="dataforge-api",
    )

    assert claims["sub"] == str(user_id)
    assert claims["type"] == "access"
    assert claims["iss"] == "dataforge-api"
    assert claims["aud"] == "dataforge-api"
    assert claims["iat"] == int(issued_at.timestamp())
    assert claims["exp"] == int(
        (issued_at + timedelta(seconds=900)).timestamp()
    )
