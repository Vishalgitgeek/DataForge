from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_authenticated_owner_id
from app.infrastructure.database import get_db_session
from app.schemas.dataset import CreateDatasetRequest, DatasetResponse
from app.services.dataset import create_dataset

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.post(
    "",
    operation_id="createDataset",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_route(
    request: CreateDatasetRequest,
    db_session: AsyncSession = Depends(get_db_session),
    owner_id: UUID = Depends(get_authenticated_owner_id),
) -> DatasetResponse:
    dataset = await create_dataset(db_session, owner_id, request)
    return DatasetResponse.model_validate(dataset)
