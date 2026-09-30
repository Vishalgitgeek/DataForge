from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UserEmailConflictError
from app.core.passwords import hash_password
from app.infrastructure.errors import is_user_email_conflict
from app.models import User
from app.schemas.auth import RegisterRequest


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
