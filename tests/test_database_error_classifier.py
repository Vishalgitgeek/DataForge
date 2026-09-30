from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.infrastructure.errors import (
    is_dataset_name_conflict,
    is_user_email_conflict,
)


class DriverError(Exception):
    def __init__(self, constraint_name: str | None = None) -> None:
        super().__init__("database constraint violation")
        self.constraint_name = constraint_name


def make_integrity_error(original: BaseException) -> IntegrityError:
    return IntegrityError("INSERT", {}, original)


def test_dataset_name_constraint_violation_is_classified_as_conflict() -> None:
    driver_error = DriverError("uq_datasets_active_owner_name")
    wrapped_error = DriverError()
    wrapped_error.__cause__ = driver_error

    assert is_dataset_name_conflict(make_integrity_error(wrapped_error)) is True


@pytest.mark.parametrize(
    "original",
    [
        DriverError("uq_refresh_tokens_token_hash"),
        DriverError("fk_datasets_owner"),
        DriverError("ck_dataset_byte_size"),
        Exception('duplicate key violates unique constraint "uq_datasets_active_owner_name"'),
    ],
)
def test_other_integrity_errors_are_not_dataset_name_conflicts(
    original: BaseException,
) -> None:
    assert is_dataset_name_conflict(make_integrity_error(original)) is False


def test_postgresql_diagnostic_constraint_name_is_supported() -> None:
    original = DriverError()
    original.diag = SimpleNamespace(
        constraint_name="uq_datasets_active_owner_name"
    )

    assert is_dataset_name_conflict(make_integrity_error(original)) is True


def test_user_email_constraint_violation_is_classified_as_conflict() -> None:
    driver_error = DriverError("users_email_key")

    assert is_user_email_conflict(make_integrity_error(driver_error)) is True


@pytest.mark.parametrize(
    "original",
    [
        DriverError("uq_refresh_tokens_token_hash"),
        DriverError("fk_users_account"),
        DriverError("ck_users_email_format"),
        Exception('duplicate key violates unique constraint "users_email_key"'),
    ],
)
def test_other_integrity_errors_are_not_user_email_conflicts(
    original: BaseException,
) -> None:
    assert is_user_email_conflict(make_integrity_error(original)) is False
