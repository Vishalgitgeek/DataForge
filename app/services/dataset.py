from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dataset_cursor import encode_dataset_cursor
from app.core.errors import DatasetNameConflictError, ResourceNotFoundError
from app.infrastructure.errors import is_dataset_name_conflict
from app.models import Dataset, DatasetVersion, DatasetVersionStatus
from app.schemas.dataset import (
    CreateDatasetRequest,
    CreateVersionRequest,
    DatasetPage,
    DatasetResponse,
    PageInfo,
    VersionPage,
    VersionResponse,
)


async def get_dataset(
    db_session: AsyncSession,
    dataset_id: UUID,
    owner_id: UUID,
) -> Dataset:
    result = await db_session.scalar(
        select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.owner_id == owner_id,
            Dataset.deleted_at.is_(None),
        )
    )
    if result is None:
        raise ResourceNotFoundError()
    return result


async def soft_delete_dataset(
    db_session: AsyncSession,
    dataset_id: UUID,
    owner_id: UUID,
) -> None:
    dataset = await db_session.scalar(
        select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.owner_id == owner_id,
            Dataset.deleted_at.is_(None),
        )
    )
    if dataset is None:
        raise ResourceNotFoundError()

    dataset.deleted_at = datetime.now(UTC)
    await db_session.flush()


async def create_dataset_version(
    db_session: AsyncSession,
    dataset_id: UUID,
    owner_id: UUID,
    request: CreateVersionRequest,
) -> DatasetVersion:
    dataset = await db_session.scalar(
        select(Dataset)
        .where(
            Dataset.id == dataset_id,
            Dataset.owner_id == owner_id,
            Dataset.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if dataset is None:
        raise ResourceNotFoundError()

    current_max = await db_session.scalar(
        select(func.max(DatasetVersion.version_number)).where(
            DatasetVersion.dataset_id == dataset_id
        )
    )
    version = DatasetVersion(
        dataset_id=dataset_id,
        version_number=(current_max or 0) + 1,
        status=DatasetVersionStatus.CREATED,
    )
    db_session.add(version)
    await db_session.flush()
    return version


async def list_dataset_versions(
    db_session: AsyncSession,
    dataset_id: UUID,
    owner_id: UUID,
    page_size: int,
    cursor: tuple[datetime, UUID] | None,
) -> VersionPage:
    dataset = await db_session.scalar(
        select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.owner_id == owner_id,
            Dataset.deleted_at.is_(None),
        )
    )
    if dataset is None:
        raise ResourceNotFoundError()

    statement = select(DatasetVersion).where(
        DatasetVersion.dataset_id == dataset_id
    )
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        statement = statement.where(
            or_(
                DatasetVersion.created_at < cursor_created_at,
                (DatasetVersion.created_at == cursor_created_at)
                & (DatasetVersion.id < cursor_id),
            )
        )

    result = await db_session.scalars(
        statement.order_by(
            DatasetVersion.created_at.desc(),
            DatasetVersion.id.desc(),
        ).limit(page_size + 1)
    )
    rows = list(result.all())
    has_more = len(rows) > page_size
    items = rows[:page_size]
    next_cursor = None
    if has_more:
        last_item = items[-1]
        next_cursor = encode_dataset_cursor(last_item.created_at, last_item.id)

    return VersionPage(
        items=[VersionResponse.model_validate(version) for version in items],
        page_info=PageInfo(next_cursor=next_cursor, has_more=has_more),
    )


async def list_datasets(
    db_session: AsyncSession,
    owner_id: UUID,
    page_size: int,
    cursor: tuple[datetime, UUID] | None,
) -> DatasetPage:
    statement = select(Dataset).where(
        Dataset.owner_id == owner_id,
        Dataset.deleted_at.is_(None),
    )
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        statement = statement.where(
            or_(
                Dataset.created_at < cursor_created_at,
                (Dataset.created_at == cursor_created_at)
                & (Dataset.id < cursor_id),
            )
        )

    result = await db_session.scalars(
        statement.order_by(Dataset.created_at.desc(), Dataset.id.desc()).limit(
            page_size + 1
        )
    )
    rows = list(result.all())
    has_more = len(rows) > page_size
    items = rows[:page_size]
    next_cursor = None
    if has_more:
        last_item = items[-1]
        next_cursor = encode_dataset_cursor(last_item.created_at, last_item.id)

    return DatasetPage(
        items=[DatasetResponse.model_validate(dataset) for dataset in items],
        page_info=PageInfo(next_cursor=next_cursor, has_more=has_more),
    )


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
