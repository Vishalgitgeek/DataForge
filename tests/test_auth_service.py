from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import UserEmailConflictError
from app.schemas.auth import RegisterRequest
from app.services.auth import register_user


@pytest.mark.anyio
async def test_register_user_adds_and_flushes_without_transaction_ownership() -> None:
    events: list[str] = []

    class FakeSession:
        def add(self, instance) -> None:
            events.append("add")

        async def flush(self) -> None:
            events.append("flush")

        async def commit(self) -> None:
            events.append("commit")

        async def rollback(self) -> None:
            events.append("rollback")

    user = await register_user(
        FakeSession(),
        RegisterRequest(email="User@Example.com", password="a" * 12),
    )

    assert user.email == "user@example.com"
    assert user.password_hash != "a" * 12
    assert events == ["add", "flush"]


@pytest.mark.anyio
async def test_register_user_translates_duplicate_email_constraint() -> None:
    driver_error = Exception("duplicate email")
    driver_error.constraint_name = "users_email_key"
    integrity_error = IntegrityError("INSERT INTO users ...", {}, driver_error)

    class FakeSession:
        def add(self, instance) -> None:
            pass

        async def flush(self) -> None:
            raise integrity_error

    with pytest.raises(UserEmailConflictError) as caught:
        await register_user(
            FakeSession(),
            RegisterRequest(email="user@example.com", password="a" * 12),
        )

    assert caught.value.__cause__ is integrity_error
