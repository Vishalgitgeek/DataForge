from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.core.dataset_cursor import decode_dataset_cursor, encode_dataset_cursor
from app.core.errors import DatasetNameConflictError, ResourceNotFoundError
from app.models import Dataset, DatasetVersionStatus
from app.schemas.dataset import CreateDatasetRequest, CreateVersionRequest, DatasetPage
from app.services.dataset import (
    create_dataset,
    create_dataset_version,
    get_dataset,
    list_datasets,
    soft_delete_dataset,
)


@pytest.mark.anyio
async def test_create_dataset_adds_and_flushes_dataset_owned_by_supplied_owner() -> None:
    owner_id = uuid4()
    request = CreateDatasetRequest(
        name="Quarterly sales",
        description="Sales by region",
    )
    events: list[str] = []
    added: list[Dataset] = []

    class FakeSession:
        def add(self, instance: Dataset) -> None:
            events.append("add")
            added.append(instance)

        async def flush(self) -> None:
            events.append("flush")

    dataset = await create_dataset(FakeSession(), owner_id, request)

    assert isinstance(dataset, Dataset)
    assert dataset is added[0]
    assert dataset.owner_id == owner_id
    assert dataset.name == request.name
    assert dataset.description == request.description
    assert events == ["add", "flush"]


@pytest.mark.anyio
async def test_create_dataset_translates_active_name_integrity_error() -> None:
    owner_id = uuid4()
    request = CreateDatasetRequest(name="Quarterly sales")
    driver_error = Exception("unique constraint violation")
    driver_error.constraint_name = "uq_datasets_active_owner_name"
    integrity_error = IntegrityError(
        "INSERT INTO datasets ...",
        {},
        driver_error,
    )

    class FakeSession:
        def add(self, _: Dataset) -> None:
            pass

        async def flush(self) -> None:
            raise integrity_error

    with pytest.raises(DatasetNameConflictError) as caught:
        await create_dataset(FakeSession(), owner_id, request)

    assert caught.value.__cause__ is integrity_error


@pytest.mark.anyio
async def test_get_dataset_returns_only_the_matching_active_owned_row() -> None:
    dataset_id = uuid4()
    owner_id = uuid4()
    returned = Dataset(id=dataset_id, owner_id=owner_id, name="Sales")
    statements = []

    class FakeSession:
        async def scalar(self, statement):
            statements.append(statement)
            return returned

    dataset = await get_dataset(FakeSession(), dataset_id, owner_id)

    assert dataset is returned
    sql = str(statements[0])
    assert "datasets.id" in sql
    assert "datasets.owner_id" in sql
    assert "datasets.deleted_at IS NULL" in sql


@pytest.mark.anyio
async def test_get_dataset_raises_generic_not_found_when_no_owned_active_row() -> None:
    class FakeSession:
        async def scalar(self, _statement):
            return None

    with pytest.raises(ResourceNotFoundError):
        await get_dataset(FakeSession(), uuid4(), uuid4())


@pytest.mark.anyio
async def test_soft_delete_dataset_scopes_by_id_owner_and_active_status() -> None:
    dataset_id = uuid4()
    owner_id = uuid4()
    created_at = datetime(2026, 10, 1, tzinfo=UTC)
    dataset = Dataset(
        id=dataset_id,
        owner_id=owner_id,
        name="Sales",
        created_at=created_at,
        updated_at=created_at,
    )
    statements = []
    events = []

    class FakeSession:
        async def scalar(self, statement):
            statements.append(statement)
            return dataset

        async def flush(self):
            events.append("flush")

    await soft_delete_dataset(FakeSession(), dataset_id, owner_id)

    sql = str(statements[0])
    assert "datasets.id" in sql
    assert "datasets.owner_id" in sql
    assert "datasets.deleted_at IS NULL" in sql
    assert dataset.deleted_at is not None
    assert dataset.deleted_at.tzinfo is not None
    assert events == ["flush"]


@pytest.mark.anyio
async def test_soft_delete_dataset_raises_not_found_when_no_active_owned_row() -> None:
    class FakeSession:
        async def scalar(self, _statement):
            return None

    with pytest.raises(ResourceNotFoundError):
        await soft_delete_dataset(FakeSession(), uuid4(), uuid4())


@pytest.mark.anyio
@pytest.mark.parametrize(("current_max", "expected_number"), [(None, 1), (1, 2), (8, 9)])
async def test_create_dataset_version_locks_owner_scoped_dataset_and_flushes(
    current_max: int | None,
    expected_number: int,
) -> None:
    dataset_id = uuid4()
    owner_id = uuid4()
    dataset = Dataset(id=dataset_id, owner_id=owner_id, name="Sales")
    statements = []
    events = []
    calls = 0
    added = []

    class FakeSession:
        async def scalar(self, statement):
            nonlocal calls
            statements.append(statement)
            calls += 1
            return dataset if calls == 1 else current_max

        def add(self, instance):
            events.append("add")
            added.append(instance)

        async def flush(self):
            events.append("flush")

    request = CreateVersionRequest(
        filename="sales.csv",
        content_type="text/csv",
        byte_size=42,
    )
    version = await create_dataset_version(
        FakeSession(),
        dataset_id,
        owner_id,
        request,
    )

    locked_select = statements[0]
    sql = str(locked_select.compile(dialect=postgresql.dialect()))
    assert "datasets.id" in sql
    assert "datasets.owner_id" in sql
    assert "datasets.deleted_at IS NULL" in sql
    assert "FOR UPDATE" in sql
    assert version is added[0]
    assert version.dataset_id == dataset_id
    assert version.version_number == expected_number
    assert version.status is DatasetVersionStatus.CREATED
    assert events == ["add", "flush"]


@pytest.mark.anyio
async def test_create_dataset_version_raises_not_found_without_inserting() -> None:
    class FakeSession:
        def __init__(self):
            self.added = []

        async def scalar(self, _statement):
            return None

        def add(self, instance):
            self.added.append(instance)

    session = FakeSession()
    with pytest.raises(ResourceNotFoundError):
        await create_dataset_version(
            session,
            uuid4(),
            uuid4(),
            CreateVersionRequest(
                filename="sales.csv",
                content_type="text/csv",
                byte_size=42,
            ),
        )
    assert session.added == []


def test_dataset_cursor_round_trips_timestamp_and_id_canonically() -> None:
    created_at = datetime(2026, 10, 1, 4, 0, 0, 123456, tzinfo=UTC)
    dataset_id = uuid4()

    cursor = encode_dataset_cursor(created_at, dataset_id)

    assert "=" not in cursor
    assert decode_dataset_cursor(cursor) == (created_at, dataset_id)


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "not-a-cursor",
        "eyJpZCI6Im5vdC1hLXV1aWQiLCJjcmVhdGVkX2F0IjoiMjAyNi0xMC0wMVQwNDowMDowMFoifQ",
        "eyJpZCI6ICJhYmMiLCAiY3JlYXRlZF9hdCI6ICJub3QtYS10aW1lIn0=",
        "eyJleHRyYSI6IngiLCJpZCI6IjAwMDAwMDAwLTAwMDAtMDAwMC0wMDAwLTAwMDAwMDAwMDAwMCIsImNyZWF0ZWRfYXQiOiIyMDI2LTEwLTAxVDA0OjAwOjAwKzAwOjAwIn0",
    ],
)
def test_dataset_cursor_decoder_rejects_invalid_or_noncanonical_values(
    cursor: str,
) -> None:
    with pytest.raises(ValueError, match="Invalid dataset cursor"):
        decode_dataset_cursor(cursor)


@pytest.mark.anyio
async def test_list_datasets_applies_owner_active_filter_keyset_order_and_page_limit() -> None:
    owner_id = uuid4()
    created_at = datetime(2026, 10, 1, tzinfo=UTC)
    datasets = [
        Dataset(id=UUID(int=3), owner_id=owner_id, name="Third", created_at=created_at, updated_at=created_at),
        Dataset(id=UUID(int=2), owner_id=owner_id, name="Second", created_at=created_at, updated_at=created_at),
    ]
    statements = []

    class ScalarResult:
        def all(self):
            return datasets

    class FakeSession:
        async def scalars(self, statement):
            statements.append(statement)
            return ScalarResult()

    cursor = (created_at, UUID(int=4))
    page = await list_datasets(FakeSession(), owner_id, 1, cursor)

    statement = statements[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "datasets.owner_id" in sql
    assert "datasets.deleted_at IS NULL" in sql
    assert "datasets.created_at <" in sql
    assert "datasets.id <" in sql
    assert "ORDER BY datasets.created_at DESC, datasets.id DESC" in sql
    assert page.items[0].id == UUID(int=3)
    assert page.page_info.has_more is True
    assert page.page_info.next_cursor is not None
    assert decode_dataset_cursor(page.page_info.next_cursor) == (
        created_at,
        UUID(int=3),
    )
