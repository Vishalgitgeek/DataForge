import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app, lifespan
from app.infrastructure import database


@pytest.mark.anyio
async def test_database_session_dependency_yields_and_closes_session(monkeypatch) -> None:
    class FakeSession:
        closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            self.closed = True

    fake_session = FakeSession()
    monkeypatch.setattr(database, "session_factory", lambda: fake_session)

    yielded = [session async for session in database.get_db_session()]

    assert yielded == [fake_session]
    assert fake_session.closed is True
    assert not isinstance(yielded[0], AsyncSession)


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
