from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.errors import InvalidCredentialsError, UserEmailConflictError
from app.core.jwt import create_access_token
from app.core.passwords import hash_password, verify_password
from app.infrastructure.errors import is_user_email_conflict
from app.models import User
from app.schemas.auth import AccessTokenResponse, LoginRequest, RegisterRequest


async def register_user(
    db_session: AsyncSession,
    request: RegisterRequest,
) -> User:
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
    )
    db_session.add(user)
    try:
        await db_session.flush()
    except IntegrityError as error:
        if is_user_email_conflict(error):
            raise UserEmailConflictError() from error
        raise
    return user


async def login_user(
    db_session: AsyncSession,
    request: LoginRequest,
) -> AccessTokenResponse:
    result = await db_session.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise InvalidCredentialsError()
    if not verify_password(request.password, user.password_hash):
        raise InvalidCredentialsError()

    settings = get_settings()
    return AccessTokenResponse(
        access_token=create_access_token(user.id),
        token_type="bearer",
        expires_in=settings.access_token_lifetime_seconds,
    )
