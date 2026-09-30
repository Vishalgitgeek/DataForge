from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_authenticated_user_id
from app.core.dataset_cursor import decode_dataset_cursor
from app.infrastructure.database import get_db_session
from app.schemas.dataset import (
    CreateDatasetRequest,
    CreateVersionRequest,
    DatasetPage,
    DatasetResponse,
    VersionPage,
    VersionResponse,
)
from app.services.dataset import (
    create_dataset,
    create_dataset_version,
    get_dataset,
    list_dataset_versions,
    list_datasets,
    soft_delete_dataset,
)

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get(
    "",
    operation_id="listDatasets",
    response_model=DatasetPage,
)
async def list_datasets_route(
    page_size: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    db_session: AsyncSession = Depends(get_db_session),
    owner_id: UUID = Depends(get_authenticated_user_id),
) -> DatasetPage:
    try:
        decoded_cursor = decode_dataset_cursor(cursor) if cursor is not None else None
    except ValueError as error:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "cursor"),
                    "msg": "Invalid cursor.",
                    "input": cursor,
                }
            ]
        ) from error

    return await list_datasets(db_session, owner_id, page_size, decoded_cursor)


@router.get(
    "/{dataset_id}",
    operation_id="getDataset",
    response_model=DatasetResponse,
)
async def get_dataset_route(
    dataset_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
    owner_id: UUID = Depends(get_authenticated_user_id),
) -> DatasetResponse:
    dataset = await get_dataset(db_session, dataset_id, owner_id)
    return DatasetResponse.model_validate(dataset)


@router.delete(
    "/{dataset_id}",
    operation_id="deleteDataset",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dataset_route(
    dataset_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
    owner_id: UUID = Depends(get_authenticated_user_id),
) -> Response:
    await soft_delete_dataset(db_session, dataset_id, owner_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{dataset_id}/versions",
    operation_id="createVersion",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_version_route(
    dataset_id: UUID,
    request: CreateVersionRequest,
    db_session: AsyncSession = Depends(get_db_session),
    owner_id: UUID = Depends(get_authenticated_user_id),
) -> VersionResponse:
    version = await create_dataset_version(
        db_session,
        dataset_id,
        owner_id,
        request,
    )
    return VersionResponse.model_validate(version)


@router.get(
    "/{dataset_id}/versions",
    operation_id="listVersions",
    response_model=VersionPage,
)
async def list_dataset_versions_route(
    dataset_id: UUID,
    page_size: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    db_session: AsyncSession = Depends(get_db_session),
    owner_id: UUID = Depends(get_authenticated_user_id),
) -> VersionPage:
    try:
        decoded_cursor = decode_dataset_cursor(cursor) if cursor is not None else None
    except ValueError as error:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "cursor"),
                    "msg": "Invalid cursor.",
                    "input": cursor,
                }
            ]
        ) from error

    return await list_dataset_versions(
        db_session,
        dataset_id,
        owner_id,
        page_size,
        decoded_cursor,
    )


@router.post(
    "",
    operation_id="createDataset",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_route(
    request: CreateDatasetRequest,
    db_session: AsyncSession = Depends(get_db_session),
    owner_id: UUID = Depends(get_authenticated_user_id),
) -> DatasetResponse:
    dataset = await create_dataset(db_session, owner_id, request)
    return DatasetResponse.model_validate(dataset)
