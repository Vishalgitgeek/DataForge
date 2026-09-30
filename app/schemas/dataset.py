from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class CreateDatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class PageInfo(BaseModel):
    next_cursor: str | None = None
    has_more: bool


class DatasetPage(BaseModel):
    items: list[DatasetResponse]
    page_info: PageInfo


class CreateVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal["text/csv"]
    byte_size: int = Field(gt=0)


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    version_number: int = Field(ge=1)
    status: Literal[
        "CREATED",
        "UPLOADING",
        "UPLOADED",
        "QUEUED",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
    ]
    created_at: AwareDatetime
    updated_at: AwareDatetime
