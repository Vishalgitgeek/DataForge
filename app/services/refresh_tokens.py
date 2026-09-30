from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    AuthenticationError,
    RefreshTokenExpiredError,
    RefreshTokenReuseError,
)
from app.core.jwt import create_access_token
from app.core.refresh_tokens import generate_refresh_token, hash_refresh_token
from app.models import RefreshToken
from app.schemas.auth import AuthResponse

REFRESH_TOKEN_LIFETIME = timedelta(days=30)


async def create_refresh_token(
    db_session: AsyncSession,
    user_id: UUID,
    family_id: UUID,
    *,
    now: datetime | None = None,
) -> tuple[str, RefreshToken]:
    if now is None:
        created_at = datetime.now(UTC)
    elif now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    else:
        created_at = now.astimezone(UTC)

    raw_token = generate_refresh_token()
    token_record = RefreshToken(
        user_id=user_id,
        family_id=family_id,
        token_hash=hash_refresh_token(raw_token),
        created_at=created_at,
        expires_at=created_at + REFRESH_TOKEN_LIFETIME,
    )
    db_session.add(token_record)
    await db_session.flush()
    return raw_token, token_record


async def rotate_refresh_token(
    db_session: AsyncSession,
    raw_token: str,
    *,
    now: datetime | None = None,
) -> AuthResponse:
    if now is None:
        current_time = datetime.now(UTC)
    elif now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    else:
        current_time = now.astimezone(UTC)

    try:
        presented_token_hash = hash_refresh_token(raw_token)
    except UnicodeEncodeError as error:
        raise AuthenticationError() from error

    result = await db_session.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == presented_token_hash)
        .with_for_update()
    )
    token_record = result.scalar_one_or_none()
    if token_record is None:
        raise AuthenticationError()
    if token_record.revoked_at is not None:
        await db_session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == token_record.family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=current_time)
        )
        raise RefreshTokenReuseError()
    if token_record.expires_at <= current_time:
        raise RefreshTokenExpiredError()

    token_record.revoked_at = current_time
    replacement_token, _ = await create_refresh_token(
        db_session,
        token_record.user_id,
        token_record.family_id,
        now=current_time,
    )
    settings = get_settings()
    return AuthResponse(
        access_token=create_access_token(token_record.user_id),
        refresh_token=replacement_token,
        token_type="bearer",
        expires_in=settings.access_token_lifetime_seconds,
    )


async def revoke_refresh_token(
    db_session: AsyncSession,
    raw_token: str,
    *,
    now: datetime | None = None,
) -> None:
    if now is None:
        revoked_at = datetime.now(UTC)
    elif now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    else:
        revoked_at = now.astimezone(UTC)

    try:
        token_hash = hash_refresh_token(raw_token)
    except UnicodeEncodeError:
        return

    await db_session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=revoked_at)
    )
