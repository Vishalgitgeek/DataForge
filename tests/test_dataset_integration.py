import os
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url

from app.api.dependencies import get_authenticated_owner_id
from app.infrastructure import database
from app.main import app
from app.models import Dataset, User

TEST_OWNER_ID = UUID("f1a7ef14-7a92-4705-9971-33060da8ba3b")
TEST_OWNER_EMAIL = "dataset-integration-owner@example.test"
DUPLICATE_TEST_OWNER_ID = UUID("3ad1be17-17cc-4df0-8d28-fc2fa32f85a1")
DUPLICATE_TEST_OWNER_EMAIL = "dataset-duplicate-integration-owner@example.test"


@pytest.mark.anyio
async def test_create_dataset_persists_to_postgresql_and_commits(monkeypatch) -> None:
    database_url = os.environ.get("DATAFORGE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set DATAFORGE_TEST_DATABASE_URL to a migrated *_test database")

    test_database_name = make_url(database_url).database
    if not test_database_name or not test_database_name.endswith("_test"):
        pytest.fail("DATAFORGE_TEST_DATABASE_URL must target a database ending in '_test'")

    engine = create_async_engine(database_url)
    test_session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    monkeypatch.setattr(database, "session_factory", test_session_factory)
    monkeypatch.setitem(
        app.dependency_overrides,
        get_authenticated_owner_id,
        lambda: TEST_OWNER_ID,
    )

    try:
        async with test_session_factory() as session:
            await session.execute(
                delete(Dataset).where(Dataset.owner_id == TEST_OWNER_ID)
            )
            await session.execute(delete(User).where(User.id == TEST_OWNER_ID))
            session.add(
                User(
                    id=TEST_OWNER_ID,
                    email=TEST_OWNER_EMAIL,
                    password_hash="integration-test-only",
                )
            )
            await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/datasets",
                json={
                    "name": "Quarterly sales",
                    "description": "Sales by region",
                },
            )

        assert response.status_code == 201
        response_body = response.json()
        dataset_id = UUID(response_body["id"])
        assert response_body["name"] == "Quarterly sales"
        assert response_body["description"] == "Sales by region"

        async with test_session_factory() as session:
            persisted_dataset = await session.scalar(
                select(Dataset).where(Dataset.id == dataset_id)
            )

        assert persisted_dataset is not None
        assert persisted_dataset.name == "Quarterly sales"
        assert persisted_dataset.description == "Sales by region"
        assert persisted_dataset.owner_id == TEST_OWNER_ID
    finally:
        async with test_session_factory() as session:
            await session.execute(
                delete(Dataset).where(Dataset.owner_id == TEST_OWNER_ID)
            )
            await session.execute(delete(User).where(User.id == TEST_OWNER_ID))
            await session.commit()
        await engine.dispose()


@pytest.mark.anyio
async def test_duplicate_dataset_name_returns_conflict_and_preserves_original(
    monkeypatch,
) -> None:
    database_url = os.environ.get("DATAFORGE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set DATAFORGE_TEST_DATABASE_URL to a migrated *_test database")

    test_database_name = make_url(database_url).database
    if not test_database_name or not test_database_name.endswith("_test"):
        pytest.fail("DATAFORGE_TEST_DATABASE_URL must target a database ending in '_test'")

    engine = create_async_engine(database_url)
    test_session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    monkeypatch.setattr(database, "session_factory", test_session_factory)
    monkeypatch.setitem(
        app.dependency_overrides,
        get_authenticated_owner_id,
        lambda: DUPLICATE_TEST_OWNER_ID,
    )

    try:
        async with test_session_factory() as session:
            await session.execute(
                delete(Dataset).where(Dataset.owner_id == DUPLICATE_TEST_OWNER_ID)
            )
            await session.execute(
                delete(User).where(User.id == DUPLICATE_TEST_OWNER_ID)
            )
            session.add(
                User(
                    id=DUPLICATE_TEST_OWNER_ID,
                    email=DUPLICATE_TEST_OWNER_EMAIL,
                    password_hash="integration-test-only",
                )
            )
            await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            first_response = await client.post(
                "/api/v1/datasets",
                json={
                    "name": "Quarterly sales",
                    "description": "Sales by region",
                },
            )
            assert first_response.status_code == 201
            original_dataset_id = UUID(first_response.json()["id"])

            request_id = "duplicate-dataset-integration-request"
            duplicate_response = await client.post(
                "/api/v1/datasets",
                headers={"X-Request-ID": request_id},
                json={
                    "name": "Quarterly sales",
                    "description": "Sales by region",
                },
            )

            assert duplicate_response.status_code == 409
            assert duplicate_response.json()["error"]["code"] == "conflict"
            assert duplicate_response.json()["error"]["retryable"] is False
            assert duplicate_response.json()["request_id"] == request_id
            assert duplicate_response.headers["X-Request-ID"] == request_id

        async with test_session_factory() as session:
            datasets = list(
                (
                    await session.scalars(
                        select(Dataset)
                        .where(Dataset.owner_id == DUPLICATE_TEST_OWNER_ID)
                        .order_by(Dataset.created_at)
                    )
                ).all()
            )

        assert len(datasets) == 1
        assert datasets[0].id == original_dataset_id
        assert datasets[0].name == "Quarterly sales"
        assert datasets[0].description == "Sales by region"
        assert datasets[0].owner_id == DUPLICATE_TEST_OWNER_ID
    finally:
        async with test_session_factory() as session:
            await session.execute(
                delete(Dataset).where(Dataset.owner_id == DUPLICATE_TEST_OWNER_ID)
            )
            await session.execute(
                delete(User).where(User.id == DUPLICATE_TEST_OWNER_ID)
            )
            await session.commit()
        await engine.dispose()
