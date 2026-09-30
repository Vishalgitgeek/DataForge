import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import get_authenticated_user_id
from app.infrastructure import database
from app.main import app
from app.models import Dataset, DatasetFile, DatasetVersion, User


def _test_database_url() -> str:
    database_url = os.environ.get("DATAFORGE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set DATAFORGE_TEST_DATABASE_URL to a migrated *_test database")
    database_name = make_url(database_url).database
    if not database_name or not database_name.endswith("_test"):
        pytest.fail("DATAFORGE_TEST_DATABASE_URL must target a database ending in '_test'")
    return database_url


async def _remove_version_test_data(
    session_factory,
    dataset_ids: list[UUID],
    owner_ids: list[UUID],
) -> None:
    async with session_factory() as session:
        await session.execute(
            delete(DatasetFile).where(
                DatasetFile.version_id.in_(
                    select(DatasetVersion.id).where(
                        DatasetVersion.dataset_id.in_(dataset_ids)
                    )
                )
            )
        )
        await session.execute(
            delete(DatasetVersion).where(
                DatasetVersion.dataset_id.in_(dataset_ids)
            )
        )
        await session.execute(delete(Dataset).where(Dataset.id.in_(dataset_ids)))
        await session.execute(delete(User).where(User.id.in_(owner_ids)))
        await session.commit()


@pytest.mark.anyio
async def test_version_creation_is_owner_scoped_and_persists_only_version_rows(
    monkeypatch,
) -> None:
    engine = create_async_engine(_test_database_url())
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "session_factory", session_factory)

    owner_id = uuid4()
    other_owner_id = uuid4()
    active_dataset_id = uuid4()
    deleted_dataset_id = uuid4()
    foreign_dataset_id = uuid4()
    owner_for_request = owner_id
    monkeypatch.setitem(
        app.dependency_overrides,
        get_authenticated_user_id,
        lambda: owner_for_request,
    )
    dataset_ids = [active_dataset_id, deleted_dataset_id, foreign_dataset_id]
    owner_ids = [owner_id, other_owner_id]

    try:
        await _remove_version_test_data(session_factory, dataset_ids, owner_ids)
        async with session_factory() as session:
            session.add_all(
                [
                    User(
                        id=owner_id,
                        email=f"version-owner-{owner_id.hex}@example.test",
                        password_hash="integration-test-only",
                    ),
                    User(
                        id=other_owner_id,
                        email=f"version-owner-{other_owner_id.hex}@example.test",
                        password_hash="integration-test-only",
                    ),
                ]
            )
            session.add_all(
                [
                    Dataset(
                        id=active_dataset_id,
                        owner_id=owner_id,
                        name="Version target",
                    ),
                    Dataset(
                        id=deleted_dataset_id,
                        owner_id=owner_id,
                        name="Version deleted target",
                        deleted_at=datetime.now(UTC),
                    ),
                    Dataset(
                        id=foreign_dataset_id,
                        owner_id=other_owner_id,
                        name="Version foreign target",
                    ),
                ]
            )
            await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            payload = {
                "filename": "sales.csv",
                "content_type": "text/csv",
                "byte_size": 42,
            }
            first_response = await client.post(
                f"/api/v1/datasets/{active_dataset_id}/versions",
                json=payload,
            )
            second_response = await client.post(
                f"/api/v1/datasets/{active_dataset_id}/versions",
                json=payload,
            )
            assert first_response.status_code == 201
            assert second_response.status_code == 201
            assert first_response.json()["version_number"] == 1
            assert second_response.json()["version_number"] == 2
            assert first_response.json()["status"] == "CREATED"
            assert second_response.json()["status"] == "CREATED"

            owner_for_request = owner_id
            missing_response = await client.post(
                "/api/v1/datasets/99999999-9999-4999-8999-999999999999/versions",
                json=payload,
            )
            deleted_response = await client.post(
                f"/api/v1/datasets/{deleted_dataset_id}/versions",
                json=payload,
            )
            owner_for_request = owner_id
            foreign_response = await client.post(
                f"/api/v1/datasets/{foreign_dataset_id}/versions",
                json=payload,
            )
            app.dependency_overrides.pop(get_authenticated_user_id, None)
            unauthenticated_response = await client.post(
                f"/api/v1/datasets/{active_dataset_id}/versions",
                json=payload,
            )

        expected_error = {
            "code": "resource_not_found",
            "message": "The requested resource was not found.",
            "retryable": False,
        }
        for response in (missing_response, deleted_response, foreign_response):
            assert response.status_code == 404
            assert response.json()["error"] == expected_error
        assert unauthenticated_response.status_code == 401
        assert unauthenticated_response.json()["error"]["code"] == (
            "authentication_required"
        )

        async with session_factory() as session:
            versions = list(
                (
                    await session.scalars(
                        select(DatasetVersion)
                        .where(DatasetVersion.dataset_id == active_dataset_id)
                        .order_by(DatasetVersion.version_number)
                    )
                ).all()
            )
            file_count = await session.scalar(
                select(func.count())
                .select_from(DatasetFile)
                .where(DatasetFile.version_id.in_([version.id for version in versions]))
            )
        assert [version.version_number for version in versions] == [1, 2]
        assert file_count == 0
    finally:
        app.dependency_overrides.pop(get_authenticated_user_id, None)
        await _remove_version_test_data(session_factory, dataset_ids, owner_ids)
        await engine.dispose()


@pytest.mark.anyio
async def test_version_creation_concurrency_is_per_dataset_and_sequential(
    monkeypatch,
) -> None:
    engine = create_async_engine(_test_database_url())
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "session_factory", session_factory)

    owner_id = uuid4()
    first_dataset_id = uuid4()
    second_dataset_id = uuid4()
    dataset_ids = [first_dataset_id, second_dataset_id]
    owner_for_request = owner_id
    monkeypatch.setitem(
        app.dependency_overrides,
        get_authenticated_user_id,
        lambda: owner_for_request,
    )
    blocker = None

    try:
        await _remove_version_test_data(session_factory, dataset_ids, [owner_id])
        async with session_factory() as session:
            session.add(
                User(
                    id=owner_id,
                    email=f"version-concurrency-{owner_id.hex}@example.test",
                    password_hash="integration-test-only",
                )
            )
            session.add_all(
                [
                    Dataset(
                        id=first_dataset_id,
                        owner_id=owner_id,
                        name="Concurrent target one",
                    ),
                    Dataset(
                        id=second_dataset_id,
                        owner_id=owner_id,
                        name="Concurrent target two",
                    ),
                ]
            )
            await session.commit()

        blocker = session_factory()
        await blocker.begin()
        await blocker.scalar(
            select(Dataset)
            .where(Dataset.id == first_dataset_id)
            .with_for_update()
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            timeout=15,
        ) as client:
            payload = {
                "filename": "concurrent.csv",
                "content_type": "text/csv",
                "byte_size": 64,
            }
            request_one = asyncio.create_task(
                client.post(
                    f"/api/v1/datasets/{first_dataset_id}/versions",
                    json=payload,
                )
            )
            request_two = asyncio.create_task(
                client.post(
                    f"/api/v1/datasets/{first_dataset_id}/versions",
                    json=payload,
                )
            )

            lock_wait_deadline = asyncio.get_running_loop().time() + 10
            blocked_queries = 0
            while asyncio.get_running_loop().time() < lock_wait_deadline:
                async with engine.connect() as connection:
                    blocked_queries = await connection.scalar(
                        text(
                            """
                            SELECT count(*)
                            FROM pg_stat_activity
                            WHERE datname = current_database()
                              AND state = 'active'
                              AND wait_event_type = 'Lock'
                              AND query ILIKE '%FROM datasets%'
                              AND query ILIKE '%FOR UPDATE%'
                            """
                        )
                    )
                if blocked_queries == 2:
                    break
                await asyncio.sleep(0.05)
            assert blocked_queries == 2
            await blocker.commit()
            responses = await asyncio.gather(request_one, request_two)
            assert [response.status_code for response in responses] == [201, 201]
            assert sorted(
                response.json()["version_number"] for response in responses
            ) == [1, 2]

            await blocker.begin()
            await blocker.scalar(
                select(Dataset)
                .where(Dataset.id == first_dataset_id)
                .with_for_update()
            )
            second_dataset_response = await asyncio.wait_for(
                client.post(
                    f"/api/v1/datasets/{second_dataset_id}/versions",
                    json=payload,
                ),
                timeout=5,
            )
            assert second_dataset_response.status_code == 201
            assert second_dataset_response.json()["version_number"] == 1
            await blocker.commit()

        async with session_factory() as session:
            first_numbers = list(
                (
                    await session.scalars(
                        select(DatasetVersion.version_number)
                        .where(DatasetVersion.dataset_id == first_dataset_id)
                        .order_by(DatasetVersion.version_number)
                    )
                ).all()
            )
            second_numbers = list(
                (
                    await session.scalars(
                        select(DatasetVersion.version_number).where(
                            DatasetVersion.dataset_id == second_dataset_id
                        )
                    )
                ).all()
            )
        assert first_numbers == [1, 2]
        assert second_numbers == [1]
    finally:
        if blocker is not None:
            await blocker.rollback()
            await blocker.close()
        await _remove_version_test_data(session_factory, dataset_ids, [owner_id])
        await engine.dispose()
