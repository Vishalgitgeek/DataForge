from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DatasetNameConflictError
from app.infrastructure.errors import is_dataset_name_conflict
from app.models import Dataset
from app.schemas.dataset import CreateDatasetRequest


async def create_dataset(
    db_session: AsyncSession,
    owner_id: UUID,
    request: CreateDatasetRequest,
) -> Dataset:
    """Create a dataset owned by the authenticated user.

    The owner is supplied by the authenticated application context, not the
    request body. The caller controls the surrounding transaction.
    """
    dataset = Dataset(
        owner_id=owner_id,
        name=request.name,
        description=request.description,
    )
    db_session.add(dataset)
    try:
        await db_session.flush()
    except IntegrityError as error:
        if is_dataset_name_conflict(error):
            raise DatasetNameConflictError() from error
        raise
    return dataset
