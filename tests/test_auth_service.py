from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import InvalidCredentialsError, UserEmailConflictError
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth import login_user, register_user


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


@pytest.mark.anyio
async def test_login_user_returns_access_token_without_transaction_ownership(
    monkeypatch,
) -> None:
    user = SimpleNamespace(id=uuid4(), is_active=True, password_hash="stored-hash")
    events: list[str] = []

    class Result:
        def scalar_one_or_none(self):
            return user

    class FakeSession:
        async def execute(self, _query):
            events.append("execute")
            return Result()

        async def commit(self) -> None:
            events.append("commit")

        async def rollback(self) -> None:
            events.append("rollback")

    monkeypatch.setattr("app.services.auth.verify_password", lambda *_args: True)
    monkeypatch.setattr(
        "app.services.auth.create_access_token",
        lambda user_id: f"token-{user_id}",
    )

    response = await login_user(
        FakeSession(),
        LoginRequest(email="  User@Example.COM  ", password="password"),
    )

    assert response.access_token == f"token-{user.id}"
    assert response.token_type == "bearer"
    assert response.expires_in == 900
    assert events == ["execute"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("user", "password_matches"),
    [
        (None, True),
        (SimpleNamespace(id=uuid4(), is_active=False, password_hash="stored"), True),
        (SimpleNamespace(id=uuid4(), is_active=True, password_hash="stored"), False),
    ],
)
async def test_login_user_uses_generic_invalid_credentials(
    monkeypatch,
    user,
    password_matches: bool,
) -> None:
    class Result:
        def scalar_one_or_none(self):
            return user

    class FakeSession:
        async def execute(self, _query):
            return Result()

    monkeypatch.setattr(
        "app.services.auth.verify_password",
        lambda *_args: password_matches,
    )

    with pytest.raises(InvalidCredentialsError) as caught:
        await login_user(
            FakeSession(),
            LoginRequest(email="user@example.com", password="password"),
        )

    assert caught.value.code == "invalid_credentials"
    assert caught.value.status_code == 401
    assert caught.value.message == "Invalid email or password."
