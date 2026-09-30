from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import RefreshTokenReuseError
from app.infrastructure.database import get_db_session
from app.infrastructure.transaction import mark_transaction_commit_on_error
from app.schemas.auth import (
    AccessTokenResponse,
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RegisterRequest,
    RefreshRequest,
    RegistrationResponse,
)
from app.services.auth import login_user, register_user
from app.services.refresh_tokens import revoke_refresh_token, rotate_refresh_token

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    operation_id="register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> RegistrationResponse:
    user = await register_user(db_session, request)
    return RegistrationResponse.model_validate(user)


@router.post(
    "/login",
    operation_id="login",
    response_model=AccessTokenResponse,
)
async def login(
    request: LoginRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> AccessTokenResponse:
    return await login_user(db_session, request)


@router.post(
    "/refresh",
    operation_id="refresh",
    response_model=AuthResponse,
)
async def refresh(
    request: RefreshRequest,
    http_request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> AuthResponse:
    try:
        return await rotate_refresh_token(db_session, request.refresh_token)
    except RefreshTokenReuseError:
        mark_transaction_commit_on_error(http_request)
        raise


@router.post(
    "/logout",
    operation_id="logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    request: LogoutRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> Response:
    await revoke_refresh_token(db_session, request.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
