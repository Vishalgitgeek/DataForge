from uuid import UUID

from fastapi import HTTPException, status


def get_authenticated_owner_id() -> UUID:
    """Provide the authenticated owner's ID once authentication is implemented."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authenticated owner dependency is not configured",
    )
