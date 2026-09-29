from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import DatasetNameConflictError
from app.models import Dataset
from app.schemas.dataset import CreateDatasetRequest
from app.services.dataset import create_dataset


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
