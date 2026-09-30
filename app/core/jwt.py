from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.core.errors import AccessTokenExpiredError, AuthenticationError


def create_access_token(
    user_id: UUID,
    *,
    now: datetime | None = None,
) -> str:
    settings = get_settings()
    if now is None:
        issued_at = datetime.now(UTC)
    elif now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    else:
        issued_at = now.astimezone(UTC)
    expires_at = issued_at + timedelta(
        seconds=settings.access_token_lifetime_seconds
    )
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iat", "sub", "iss", "aud", "type"]},
        )
    except jwt.ExpiredSignatureError as error:
        raise AccessTokenExpiredError() from error
    except jwt.InvalidTokenError as error:
        raise AuthenticationError() from error

    if not isinstance(payload, dict):
        raise AuthenticationError()
    if payload.get("type") != "access":
        raise AuthenticationError()

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise AuthenticationError()
    try:
        return UUID(subject)
    except ValueError as error:
        raise AuthenticationError() from error
