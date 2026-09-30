from uuid import UUID

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AuthenticationError
from app.core.jwt import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_authenticated_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> UUID:
    if credentials is None:
        raise AuthenticationError()
    return decode_access_token(credentials.credentials)


def get_authenticated_owner_id() -> UUID:
    """Provide the authenticated owner's ID once authentication is implemented."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authenticated owner dependency is not configured",
    )
