import os
from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url

from app.api.dependencies import get_authenticated_user_id
from app.infrastructure import database
from app.main import app
from app.models import (
    Dataset,
    DatasetVersion,
    DatasetVersionStatus,
    JobStatus,
    ProcessingJob,
    QueryHistory,
    QueryStatus,
    User,
)

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
        get_authenticated_user_id,
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
        get_authenticated_user_id,
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


@pytest.mark.anyio
async def test_get_dataset_is_owner_scoped_and_hides_soft_deleted_rows(
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

    owner_id = UUID("bc7c779f-614d-44ef-86de-9f88f4f41d6d")
    other_owner_id = UUID("d60e8c4f-caa5-48fc-a1e5-98a24c8cb9a7")
    active_dataset_id = UUID("d389e2f9-beb9-4235-a7ac-3b1fcd38d49e")
    deleted_dataset_id = UUID("8dcf4b14-df68-4d36-a89e-c10aaab9f56c")
    active_user_id = owner_id
    monkeypatch.setitem(
        app.dependency_overrides,
        get_authenticated_user_id,
        lambda: active_user_id,
    )

    try:
        async with test_session_factory() as session:
            await session.execute(
                delete(Dataset).where(
                    Dataset.id.in_([active_dataset_id, deleted_dataset_id])
                )
            )
            await session.execute(
                delete(User).where(User.id.in_([owner_id, other_owner_id]))
            )
            session.add_all(
                [
                    User(
                        id=owner_id,
                        email=f"dataset-owner-{owner_id.hex}@example.com",
                        password_hash="integration-test-only",
                    ),
                    User(
                        id=other_owner_id,
                        email=f"dataset-other-owner-{other_owner_id.hex}@example.com",
                        password_hash="integration-test-only",
                    ),
                ]
            )
            session.add_all(
                [
                    Dataset(
                        id=active_dataset_id,
                        owner_id=owner_id,
                        name="Owner scoped active",
                    ),
                    Dataset(
                        id=deleted_dataset_id,
                        owner_id=owner_id,
                        name="Owner scoped deleted",
                        deleted_at=datetime.now(UTC),
                    ),
                ]
            )
            await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            active_response = await client.get(
                f"/api/v1/datasets/{active_dataset_id}"
            )
            active_user_id = other_owner_id
            other_owner_response = await client.get(
                f"/api/v1/datasets/{active_dataset_id}"
            )
            active_user_id = owner_id
            deleted_response = await client.get(
                f"/api/v1/datasets/{deleted_dataset_id}"
            )

        assert active_response.status_code == 200
        assert active_response.json()["id"] == str(active_dataset_id)
        assert other_owner_response.status_code == 404
        assert deleted_response.status_code == 404
        assert other_owner_response.json()["error"] == {
            "code": "resource_not_found",
            "message": "The requested resource was not found.",
            "retryable": False,
        }
        assert other_owner_response.json()["error"] == deleted_response.json()["error"]
    finally:
        async with test_session_factory() as session:
            await session.execute(
                delete(Dataset).where(
                    Dataset.id.in_([active_dataset_id, deleted_dataset_id])
                )
            )
            await session.execute(
                delete(User).where(User.id.in_([owner_id, other_owner_id]))
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.anyio
async def test_list_datasets_cursor_paginates_in_owner_scoped_newest_first_order(
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

    owner_id = UUID("19de1326-8c07-40b7-b105-fb27d25a0612")
    other_owner_id = UUID("e94fd113-0c4f-4c37-95af-78ab9df3f544")
    dataset_ids = [
        UUID("00000000-0000-0000-0000-000000000020"),
        UUID("00000000-0000-0000-0000-000000000010"),
        UUID("00000000-0000-0000-0000-000000000015"),
        UUID("00000000-0000-0000-0000-000000000005"),
        UUID("00000000-0000-0000-0000-000000000030"),
        UUID("00000000-0000-0000-0000-000000000040"),
    ]
    newest_timestamp = datetime(2026, 10, 1, 4, 0, tzinfo=UTC)
    older_timestamp = datetime(2026, 10, 1, 3, 0, tzinfo=UTC)
    monkeypatch.setitem(
        app.dependency_overrides,
        get_authenticated_user_id,
        lambda: owner_id,
    )

    try:
        async with test_session_factory() as session:
            await session.execute(delete(Dataset).where(Dataset.id.in_(dataset_ids)))
            await session.execute(
                delete(User).where(User.id.in_([owner_id, other_owner_id]))
            )
            session.add_all(
                [
                    User(
                        id=owner_id,
                        email=f"dataset-list-owner-{owner_id.hex}@example.com",
                        password_hash="integration-test-only",
                    ),
                    User(
                        id=other_owner_id,
                        email=f"dataset-list-other-{other_owner_id.hex}@example.com",
                        password_hash="integration-test-only",
                    ),
                ]
            )
            session.add_all(
                [
                    Dataset(
                        id=dataset_ids[0],
                        owner_id=owner_id,
                        name="Newest tie high id",
                        created_at=newest_timestamp,
                        updated_at=newest_timestamp,
                    ),
                    Dataset(
                        id=dataset_ids[1],
                        owner_id=owner_id,
                        name="Newest tie low id",
                        created_at=newest_timestamp,
                        updated_at=newest_timestamp,
                    ),
                    Dataset(
                        id=dataset_ids[2],
                        owner_id=owner_id,
                        name="Older tie high id",
                        created_at=older_timestamp,
                        updated_at=older_timestamp,
                    ),
                    Dataset(
                        id=dataset_ids[3],
                        owner_id=owner_id,
                        name="Older tie low id",
                        created_at=older_timestamp,
                        updated_at=older_timestamp,
                    ),
                    Dataset(
                        id=dataset_ids[4],
                        owner_id=owner_id,
                        name="Soft deleted newest",
                        created_at=newest_timestamp.replace(hour=5),
                        updated_at=newest_timestamp,
                        deleted_at=newest_timestamp,
                    ),
                    Dataset(
                        id=dataset_ids[5],
                        owner_id=other_owner_id,
                        name="Other owner newest",
                        created_at=newest_timestamp.replace(hour=6),
                        updated_at=newest_timestamp,
                    ),
                ]
            )
            await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            first_page = await client.get(
                "/api/v1/datasets",
                params={"page_size": 2},
            )
            assert first_page.status_code == 200
            first_body = first_page.json()
            assert [item["id"] for item in first_body["items"]] == [
                str(dataset_ids[0]),
                str(dataset_ids[1]),
            ]
            assert first_body["page_info"]["has_more"] is True
            cursor = first_body["page_info"]["next_cursor"]
            assert cursor

            second_page = await client.get(
                "/api/v1/datasets",
                params={"page_size": 2, "cursor": cursor},
            )
            assert second_page.status_code == 200
            second_body = second_page.json()
            assert [item["id"] for item in second_body["items"]] == [
                str(dataset_ids[2]),
                str(dataset_ids[3]),
            ]
            assert second_body["page_info"] == {
                "next_cursor": None,
                "has_more": False,
            }

            monkeypatch.setitem(
                app.dependency_overrides,
                get_authenticated_user_id,
                lambda: other_owner_id,
            )
            other_owner_page = await client.get("/api/v1/datasets")

        assert other_owner_page.status_code == 200
        assert [item["id"] for item in other_owner_page.json()["items"]] == [
            str(dataset_ids[5])
        ]
    finally:
        async with test_session_factory() as session:
            await session.execute(delete(Dataset).where(Dataset.id.in_(dataset_ids)))
            await session.execute(
                delete(User).where(User.id.in_([owner_id, other_owner_id]))
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.anyio
async def test_delete_dataset_soft_deletes_only_active_owned_dataset_and_preserves_relations(
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

    owner_id = UUID("6d9b4e41-7453-44a8-8587-149bec7bd441")
    other_owner_id = UUID("46d012a9-791c-4bf3-bf74-b67e7a4fed54")
    dataset_id = UUID("0f04fd80-57df-41a8-8279-5fc5a70e2172")
    deleted_dataset_id = UUID("63cd0982-1ae4-4a9e-a1be-27efdc58a37f")
    other_active_dataset_id = UUID("78cf3058-5c5c-49ee-a31b-92baac039957")
    version_id = UUID("34702eb0-c1bd-45af-a4eb-674e9a98a1a0")
    job_id = UUID("459f520e-0a2f-4201-85ae-9bfde846d69a")
    history_id = UUID("568f98c1-bd29-4d57-85c6-521a8660ae28")
    original_updated_at = datetime(2020, 1, 1, tzinfo=UTC)
    owner_for_request = owner_id
    monkeypatch.setitem(
        app.dependency_overrides,
        get_authenticated_user_id,
        lambda: owner_for_request,
    )

    async def clean_test_rows() -> None:
        async with test_session_factory() as session:
            await session.execute(delete(QueryHistory).where(QueryHistory.id == history_id))
            await session.execute(delete(ProcessingJob).where(ProcessingJob.id == job_id))
            await session.execute(
                delete(DatasetVersion).where(DatasetVersion.id == version_id)
            )
            await session.execute(
                delete(Dataset).where(
                    Dataset.id.in_(
                        [dataset_id, deleted_dataset_id, other_active_dataset_id]
                    )
                )
            )
            await session.execute(
                delete(User).where(User.id.in_([owner_id, other_owner_id]))
            )
            await session.commit()

    try:
        await clean_test_rows()
        async with test_session_factory() as session:
            session.add_all(
                [
                    User(
                        id=owner_id,
                        email=f"dataset-delete-owner-{owner_id.hex}@example.com",
                        password_hash="integration-test-only",
                    ),
                    User(
                        id=other_owner_id,
                        email=f"dataset-delete-other-{other_owner_id.hex}@example.com",
                        password_hash="integration-test-only",
                    ),
                ]
            )
            session.add_all(
                [
                    Dataset(
                        id=dataset_id,
                        owner_id=owner_id,
                        name="Dataset to soft delete",
                        created_at=original_updated_at,
                        updated_at=original_updated_at,
                    ),
                    Dataset(
                        id=deleted_dataset_id,
                        owner_id=owner_id,
                        name="Already soft deleted",
                        created_at=original_updated_at,
                        updated_at=original_updated_at,
                        deleted_at=original_updated_at,
                    ),
                    Dataset(
                        id=other_active_dataset_id,
                        owner_id=owner_id,
                        name="Keep active",
                        created_at=original_updated_at,
                        updated_at=original_updated_at,
                    ),
                    DatasetVersion(
                        id=version_id,
                        dataset_id=dataset_id,
                        version_number=1,
                        status=DatasetVersionStatus.CREATED,
                    ),
                    ProcessingJob(
                        id=job_id,
                        version_id=version_id,
                        job_type="integration",
                        status=JobStatus.PENDING,
                        max_attempts=3,
                        idempotency_key="dataset-soft-delete-integration",
                    ),
                    QueryHistory(
                        id=history_id,
                        user_id=owner_id,
                        version_id=version_id,
                        request_payload={},
                        normalized_query_hash="a" * 64,
                        status=QueryStatus.SUCCEEDED,
                    ),
                ]
            )
            await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            delete_response = await client.delete(f"/api/v1/datasets/{dataset_id}")
            assert delete_response.status_code == 204
            assert delete_response.content == b""

            after_delete_get = await client.get(f"/api/v1/datasets/{dataset_id}")
            after_delete_list = await client.get("/api/v1/datasets")

            owner_for_request = other_owner_id
            foreign_owner_response = await client.delete(
                f"/api/v1/datasets/{other_active_dataset_id}"
            )
            owner_for_request = owner_id
            missing_response = await client.delete(
                "/api/v1/datasets/99999999-9999-4999-8999-999999999999"
            )
            deleted_response = await client.delete(
                f"/api/v1/datasets/{deleted_dataset_id}"
            )

        generic_not_found = {
            "code": "resource_not_found",
            "message": "The requested resource was not found.",
            "retryable": False,
        }
        assert after_delete_get.status_code == 404
        assert after_delete_list.status_code == 200
        assert [item["id"] for item in after_delete_list.json()["items"]] == [
            str(other_active_dataset_id)
        ]
        for response in (foreign_owner_response, missing_response, deleted_response):
            assert response.status_code == 404
            assert response.json()["error"] == generic_not_found

        async with test_session_factory() as session:
            persisted_dataset = await session.scalar(
                select(Dataset).where(Dataset.id == dataset_id)
            )
            persisted_version = await session.scalar(
                select(DatasetVersion).where(DatasetVersion.id == version_id)
            )
            persisted_job = await session.scalar(
                select(ProcessingJob).where(ProcessingJob.id == job_id)
            )
            persisted_history = await session.scalar(
                select(QueryHistory).where(QueryHistory.id == history_id)
            )

        assert persisted_dataset is not None
        assert persisted_dataset.deleted_at is not None
        assert persisted_dataset.deleted_at.tzinfo is not None
        assert persisted_dataset.updated_at > original_updated_at
        assert persisted_version is not None
        assert persisted_job is not None
        assert persisted_history is not None
    finally:
        await clean_test_rows()
        await engine.dispose()
