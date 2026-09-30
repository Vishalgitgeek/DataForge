from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.dataset import (
    CreateDatasetRequest,
    CreateVersionRequest,
    DatasetResponse,
    VersionResponse,
)


def test_create_dataset_request_trims_name_and_accepts_optional_description() -> None:
    request = CreateDatasetRequest.model_validate(
        {"name": "  Sales data  ", "description": "Quarterly sales"}
    )

    assert request.name == "Sales data"
    assert request.description == "Quarterly sales"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   "},
        {"name": "x" * 256},
        {"name": "Valid name", "description": "x" * 2001},
        {"name": "Valid name", "owner_id": str(uuid4())},
    ],
)
def test_create_dataset_request_rejects_invalid_input(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        CreateDatasetRequest.model_validate(payload)


def test_dataset_response_validates_public_fields_from_attributes() -> None:
    now = datetime.now(UTC)

    class DatasetRecord:
        id = uuid4()
        name = "Sales data"
        description = None
        created_at = now
        updated_at = now
        owner_id = uuid4()
        deleted_at = None

    response = DatasetResponse.model_validate(DatasetRecord())

    assert response.id == DatasetRecord.id
    assert response.name == "Sales data"
    assert response.description is None
    assert response.created_at == now
    assert response.updated_at == now
    assert "owner_id" not in response.model_dump()


def test_create_version_request_accepts_documented_csv_fields() -> None:
    request = CreateVersionRequest(
        filename="sales.csv",
        content_type="text/csv",
        byte_size=1,
    )

    assert request.filename == "sales.csv"
    assert request.content_type == "text/csv"
    assert request.byte_size == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"filename": "", "content_type": "text/csv", "byte_size": 1},
        {"filename": "x" * 256, "content_type": "text/csv", "byte_size": 1},
        {"filename": "sales.csv", "content_type": "application/json", "byte_size": 1},
        {"filename": "sales.csv", "content_type": "text/csv", "byte_size": 0},
        {"filename": "sales.csv", "content_type": "text/csv", "byte_size": -1},
        {"filename": "sales.csv", "content_type": "text/csv", "byte_size": 1, "dataset_id": str(uuid4())},
    ],
)
def test_create_version_request_rejects_invalid_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CreateVersionRequest.model_validate(payload)


def test_version_response_uses_public_contract_fields() -> None:
    now = datetime.now(UTC)
    version = VersionResponse(
        id=uuid4(),
        dataset_id=uuid4(),
        version_number=1,
        status="CREATED",
        created_at=now,
        updated_at=now,
    )

    assert version.status == "CREATED"
