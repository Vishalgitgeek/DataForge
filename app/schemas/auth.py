from datetime import datetime
from uuid import UUID
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
)


def strip_email(value: str) -> str:
    return value.strip()


def normalize_email(value: EmailStr) -> str:
    return str(value).lower()


NormalizedEmail = Annotated[
    EmailStr,
    BeforeValidator(strip_email),
    AfterValidator(normalize_email),
]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: NormalizedEmail
    password: str = Field(min_length=12)


class RegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    created_at: datetime
