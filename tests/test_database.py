import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.main import app, lifespan
from app.infrastructure import database


@pytest.mark.anyio
async def test_database_session_dependency_yields_middleware_session() -> None:
    class FakeSession:
        committed = False
        rolled_back = False

    fake_session = FakeSession()
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )
    request.state.db_session = fake_session

    yielded = [session async for session in database.get_db_session(request)]

    assert yielded == [fake_session]
    assert fake_session.committed is False
    assert fake_session.rolled_back is False
    assert not isinstance(yielded[0], AsyncSession)


@pytest.mark.anyio
async def test_database_session_dependency_does_not_own_transaction_or_close() -> None:
    class FakeSession:
        committed = False
        rolled_back = False
        closed = False

    fake_session = FakeSession()
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )
    request.state.db_session = fake_session
    session_generator = database.get_db_session(request)

    assert await anext(session_generator) is fake_session
    with pytest.raises(RuntimeError, match="request failed"):
        await session_generator.athrow(RuntimeError("request failed"))

    assert fake_session.committed is False
    assert fake_session.rolled_back is False
    assert fake_session.closed is False


@pytest.mark.anyio
async def test_application_lifespan_disposes_database(monkeypatch) -> None:
    disposed = False

    async def fake_dispose() -> None:
        nonlocal disposed
        disposed = True

    monkeypatch.setattr("app.main.dispose_database", fake_dispose)

    async with lifespan(app):
        assert disposed is False

    assert disposed is True
