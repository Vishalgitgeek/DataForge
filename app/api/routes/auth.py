from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_db_session
from app.schemas.auth import RegisterRequest, RegistrationResponse
from app.services.auth import register_user

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
