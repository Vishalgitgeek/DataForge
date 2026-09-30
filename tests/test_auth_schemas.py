import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest


def test_register_request_normalizes_email_and_accepts_minimum_password() -> None:
    request = RegisterRequest(
        email="  User@Example.COM ",
        password="a" * 12,
    )

    assert request.email == "user@example.com"
    assert isinstance(request.email, str)


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "a" * 12},
        {"email": "user@example.com", "password": "a" * 11},
        {"email": "user@example.com", "password": "a" * 12, "extra": True},
    ],
)
def test_register_request_rejects_invalid_input(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate(payload)
