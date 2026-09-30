import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure import database
from app.main import app
from app.models import RefreshToken, User
from app.core.refresh_tokens import hash_refresh_token


@pytest.mark.anyio
async def test_reused_refresh_token_family_revocation_commits_with_401(
    monkeypatch,
) -> None:
    database_url = os.environ.get("DATAFORGE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set DATAFORGE_TEST_DATABASE_URL to a migrated *_test database")

    database_name = make_url(database_url).database
    if not database_name or not database_name.endswith("_test"):
        pytest.fail("DATAFORGE_TEST_DATABASE_URL must target a database ending in '_test'")

    engine = create_async_engine(database_url)
    test_session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    monkeypatch.setattr(database, "session_factory", test_session_factory)

    user_id = uuid4()
    family_id = uuid4()
    other_family_id = uuid4()
    presented_token = f"reused-token-{uuid4()}"
    now = datetime.now(UTC)
    try:
        async with test_session_factory() as session:
            session.add(
                User(
                    id=user_id,
                    email=f"refresh-reuse-{user_id.hex}@example.com",
                    password_hash="integration-test-only",
                )
            )
            session.add_all(
                [
                    RefreshToken(
                        user_id=user_id,
                        family_id=family_id,
                        token_hash=hash_refresh_token(presented_token),
                        expires_at=now + timedelta(days=5),
                        revoked_at=now - timedelta(minutes=1),
                        created_at=now - timedelta(days=1),
                    ),
                    RefreshToken(
                        user_id=user_id,
                        family_id=family_id,
                        token_hash=hash_refresh_token(f"active-{uuid4()}"),
                        expires_at=now + timedelta(days=10),
                        created_at=now,
                    ),
                    RefreshToken(
                        user_id=user_id,
                        family_id=other_family_id,
                        token_hash=hash_refresh_token(f"other-{uuid4()}"),
                        expires_at=now + timedelta(days=10),
                        created_at=now,
                    ),
                ]
            )
            await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": presented_token},
            )

        assert response.status_code == 401
        assert response.json()["error"] == {
            "code": "authentication_required",
            "message": "Authentication is required.",
            "retryable": False,
        }

        async with test_session_factory() as session:
            tokens = list(
                (
                    await session.scalars(
                        select(RefreshToken).where(
                            RefreshToken.user_id == user_id
                        )
                    )
                ).all()
            )
        family_tokens = [token for token in tokens if token.family_id == family_id]
        other_family_tokens = [
            token for token in tokens if token.family_id == other_family_id
        ]
        assert len(family_tokens) == 2
        assert all(token.revoked_at is not None for token in family_tokens)
        assert len(other_family_tokens) == 1
        assert other_family_tokens[0].revoked_at is None
    finally:
        async with test_session_factory() as session:
            await session.execute(
                delete(RefreshToken).where(RefreshToken.user_id == user_id)
            )
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_refresh_requests_serialize_and_revoke_family(
    monkeypatch,
) -> None:
    database_url = os.environ.get("DATAFORGE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set DATAFORGE_TEST_DATABASE_URL to a migrated *_test database")

    database_name = make_url(database_url).database
    if not database_name or not database_name.endswith("_test"):
        pytest.fail("DATAFORGE_TEST_DATABASE_URL must target a database ending in '_test'")

    engine = create_async_engine(database_url)
    query_started: asyncio.Queue[None] = asyncio.Queue()
    observe_request_queries = False

    class ObservedSession(AsyncSession):
        async def execute(self, statement, *args, **kwargs):
            if observe_request_queries:
                query_started.put_nowait(None)
            return await super().execute(statement, *args, **kwargs)

    test_session_factory = async_sessionmaker(
        bind=engine,
        class_=ObservedSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr(database, "session_factory", test_session_factory)

    user_id = uuid4()
    family_id = uuid4()
    raw_token = f"concurrent-refresh-{uuid4()}"
    token_hash = hash_refresh_token(raw_token)
    now = datetime.now(UTC)
    holder = None
    try:
        async with test_session_factory() as seed_session:
            seed_session.add(
                User(
                    id=user_id,
                    email=f"refresh-concurrency-{user_id.hex}@example.com",
                    password_hash="integration-test-only",
                )
            )
            seed_session.add(
                RefreshToken(
                    user_id=user_id,
                    family_id=family_id,
                    token_hash=token_hash,
                    expires_at=now + timedelta(days=10),
                    created_at=now,
                )
            )
            await seed_session.commit()

        holder = test_session_factory()
        await holder.execute(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .with_for_update()
        )
        observe_request_queries = True

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            request_one = asyncio.create_task(
                client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": raw_token},
                )
            )
            request_two = asyncio.create_task(
                client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": raw_token},
                )
            )

            await asyncio.wait_for(
                asyncio.gather(query_started.get(), query_started.get()),
                timeout=10,
            )
            lock_wait_deadline = asyncio.get_running_loop().time() + 10
            blocked_refresh_queries = 0
            while asyncio.get_running_loop().time() < lock_wait_deadline:
                async with engine.connect() as connection:
                    blocked_refresh_queries = await connection.scalar(
                        text(
                            """
                            SELECT count(*)
                            FROM pg_stat_activity
                            WHERE datname = current_database()
                              AND state = 'active'
                              AND wait_event_type = 'Lock'
                              AND query ILIKE '%refresh_tokens%'
                              AND query ILIKE '%FOR UPDATE%'
                            """
                        )
                    )
                if blocked_refresh_queries == 2:
                    break
                await asyncio.sleep(0.05)
            assert blocked_refresh_queries == 2
            await holder.commit()
            responses = await asyncio.gather(request_one, request_two)

        assert sorted(response.status_code for response in responses) == [200, 401]
        successful_response = next(
            response for response in responses if response.status_code == 200
        )
        rejected_response = next(
            response for response in responses if response.status_code == 401
        )
        assert successful_response.json()["refresh_token"] != raw_token
        assert rejected_response.json()["error"] == {
            "code": "authentication_required",
            "message": "Authentication is required.",
            "retryable": False,
        }

        async with test_session_factory() as verify_session:
            family_tokens = list(
                (
                    await verify_session.scalars(
                        select(RefreshToken).where(
                            RefreshToken.family_id == family_id
                        )
                    )
                ).all()
            )
        assert len(family_tokens) == 2
        assert all(token.revoked_at is not None for token in family_tokens)
        assert not any(token.revoked_at is None for token in family_tokens)
        assert sum(token.token_hash == token_hash for token in family_tokens) == 1
    finally:
        observe_request_queries = False
        if holder is not None:
            if holder.in_transaction():
                await holder.rollback()
            await holder.close()
        async with test_session_factory() as cleanup_session:
            await cleanup_session.execute(
                delete(RefreshToken).where(RefreshToken.user_id == user_id)
            )
            await cleanup_session.execute(delete(User).where(User.id == user_id))
            await cleanup_session.commit()
        await engine.dispose()
