import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url

from app.infrastructure import database
from app.main import app
from app.models import User

TEST_EMAIL = "registration-integration@example.com"


@pytest.mark.anyio
async def test_registration_persists_hash_and_rejects_duplicate_email(monkeypatch) -> None:
    database_url = os.environ.get("DATAFORGE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set DATAFORGE_TEST_DATABASE_URL to a migrated *_test database")

    database_name = make_url(database_url).database
    if not database_name or not database_name.endswith("_test"):
        pytest.fail("DATAFORGE_TEST_DATABASE_URL must target a database ending in '_test'")

    engine = create_async_engine(database_url)
    test_session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "session_factory", test_session_factory)

    try:
        async with test_session_factory() as session:
            await session.execute(delete(User).where(User.email == TEST_EMAIL))
            await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            first_response = await client.post(
                "/api/v1/auth/register",
                json={"email": f"  {TEST_EMAIL.upper()}  ", "password": "a" * 12},
            )
            duplicate_response = await client.post(
                "/api/v1/auth/register",
                headers={"X-Request-ID": "duplicate-registration-request"},
                json={"email": TEST_EMAIL, "password": "different password"},
            )

        assert first_response.status_code == 201
        assert first_response.json()["email"] == TEST_EMAIL
        assert "password" not in first_response.json()
        assert "password_hash" not in first_response.json()

        assert duplicate_response.status_code == 409
        assert duplicate_response.json()["error"] == {
            "code": "conflict",
            "message": "An account with this email already exists.",
            "retryable": False,
        }
        assert duplicate_response.json()["request_id"] == "duplicate-registration-request"

        async with test_session_factory() as session:
            users = list(
                (
                    await session.scalars(
                        select(User).where(User.email == TEST_EMAIL)
                    )
                ).all()
            )

        assert len(users) == 1
        assert users[0].email == TEST_EMAIL
        assert users[0].password_hash != "a" * 12
        assert users[0].password_hash.startswith("$argon2id$")
    finally:
        async with test_session_factory() as session:
            await session.execute(delete(User).where(User.email == TEST_EMAIL))
            await session.commit()
        await engine.dispose()
