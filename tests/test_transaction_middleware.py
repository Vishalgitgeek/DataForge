import pytest
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from starlette.responses import Response

from app.core.errors import DatasetNameConflictError
from app.infrastructure import database
from app.infrastructure.transaction import (
    mark_transaction_commit_on_error,
    transaction_middleware,
)


def make_request() -> Request:  
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/datasets",
            "raw_path": b"/api/v1/datasets",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rollback_count = 0
        self.closed = False
        self.commit_error: BaseException | None = None
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")
        if self.commit_error is not None:
            raise self.commit_error
        self.committed = True

    async def rollback(self) -> None:
        self.events.append("rollback")
        self.rollback_count += 1

    async def close(self) -> None:
        self.events.append("close")
        self.closed = True


def install_session_factory(
    monkeypatch,
    *,
    commit_error: BaseException | None = None,
) -> list[FakeSession]:
    sessions: list[FakeSession] = []

    def create_session() -> FakeSession:
        session = FakeSession()
        session.commit_error = commit_error
        sessions.append(session)
        return session

    monkeypatch.setattr(database, "session_factory", create_session)
    return sessions


@pytest.mark.anyio
async def test_transaction_middleware_commits_success_and_closes_session(
    monkeypatch,
) -> None:
    sessions = install_session_factory(monkeypatch)
    downstream_sessions: list[FakeSession] = []

    async def downstream(request: Request) -> Response:
        request.state.db_session.events.append("downstream")
        downstream_sessions.append(request.state.db_session)
        return Response("ok", status_code=200)

    response = await transaction_middleware(make_request(), downstream)

    assert response.status_code == 200
    assert len(sessions) == 1
    session = sessions[0]
    assert downstream_sessions == [session]
    assert session.committed is True
    assert session.rollback_count == 0
    assert session.closed is True
    assert session.events == ["downstream", "commit", "close"]


@pytest.mark.anyio
async def test_transaction_middleware_rolls_back_downstream_exception_and_propagates(
    monkeypatch,
) -> None:
    sessions = install_session_factory(monkeypatch)
    failure = RuntimeError("downstream failed")

    async def downstream(request: Request) -> Response:
        request.state.db_session.events.append("downstream")
        raise failure

    with pytest.raises(RuntimeError) as caught:
        await transaction_middleware(make_request(), downstream)

    assert caught.value is failure
    assert len(sessions) == 1
    session = sessions[0]
    assert session.committed is False
    assert session.rollback_count == 1
    assert session.closed is True
    assert session.events == ["downstream", "rollback", "close"]


@pytest.mark.anyio
async def test_transaction_middleware_rolls_back_and_propagates_commit_integrity_error(
    monkeypatch,
) -> None:
    commit_error = IntegrityError(
        "INSERT INTO datasets ...",
        {},
        Exception("duplicate key violates uq_datasets_active_owner_name"),
    )
    sessions = install_session_factory(monkeypatch, commit_error=commit_error)

    async def downstream(request: Request) -> Response:
        request.state.db_session.events.append("downstream")
        return Response("ok", status_code=201)

    with pytest.raises(IntegrityError) as caught:
        await transaction_middleware(make_request(), downstream)

    assert caught.value is commit_error
    assert len(sessions) == 1
    assert sessions[0].committed is False
    assert sessions[0].rollback_count == 1
    assert sessions[0].closed is True
    assert sessions[0].events == ["downstream", "commit", "rollback", "close"]


@pytest.mark.anyio
async def test_transaction_middleware_translates_known_dataset_name_conflict(
    monkeypatch,
) -> None:
    driver_error = Exception("unique constraint violation")
    driver_error.constraint_name = "uq_datasets_active_owner_name"
    wrapped_error = Exception("database integrity violation")
    wrapped_error.__cause__ = driver_error
    commit_error = IntegrityError("INSERT INTO datasets ...", {}, wrapped_error)
    sessions = install_session_factory(monkeypatch, commit_error=commit_error)

    async def downstream(_: Request) -> Response:
        return Response("ok", status_code=201)

    with pytest.raises(DatasetNameConflictError):
        await transaction_middleware(make_request(), downstream)

    assert len(sessions) == 1
    assert sessions[0].committed is False
    assert sessions[0].rollback_count == 1
    assert sessions[0].closed is True
    assert sessions[0].events == ["commit", "rollback", "close"]


@pytest.mark.anyio
async def test_transaction_middleware_preserves_downstream_dataset_name_conflict(
    monkeypatch,
) -> None:
    conflict_error = DatasetNameConflictError()
    sessions = install_session_factory(monkeypatch)

    async def downstream(_: Request) -> Response:
        raise conflict_error

    with pytest.raises(DatasetNameConflictError) as caught:
        await transaction_middleware(make_request(), downstream)

    assert caught.value is conflict_error
    assert len(sessions) == 1
    assert sessions[0].committed is False
    assert sessions[0].rollback_count == 1
    assert sessions[0].closed is True
    assert sessions[0].events == ["rollback", "close"]


@pytest.mark.anyio
async def test_transaction_middleware_rolls_back_handled_conflict_response(
    monkeypatch,
) -> None:
    sessions = install_session_factory(monkeypatch)

    async def downstream(request: Request) -> Response:
        request.state.db_session.events.append("downstream")
        return Response(status_code=409)

    response = await transaction_middleware(make_request(), downstream)

    assert response.status_code == 409
    assert len(sessions) == 1
    assert sessions[0].committed is False
    assert sessions[0].rollback_count == 1
    assert sessions[0].closed is True
    assert sessions[0].events == ["downstream", "rollback", "close"]


@pytest.mark.anyio
async def test_transaction_middleware_rolls_back_server_error_response(
    monkeypatch,
) -> None:
    sessions = install_session_factory(monkeypatch)

    async def downstream(_: Request) -> Response:
        return Response(status_code=503)

    response = await transaction_middleware(make_request(), downstream)

    assert response.status_code == 503
    assert sessions[0].committed is False
    assert sessions[0].rollback_count == 1
    assert sessions[0].closed is True
    assert sessions[0].events == ["rollback", "close"]


@pytest.mark.anyio
async def test_transaction_middleware_commits_marked_unauthorized_response(
    monkeypatch,
) -> None:
    sessions = install_session_factory(monkeypatch)

    async def downstream(request: Request) -> Response:
        mark_transaction_commit_on_error(request)
        return Response(status_code=401)

    response = await transaction_middleware(make_request(), downstream)

    assert response.status_code == 401
    assert sessions[0].committed is True
    assert sessions[0].rollback_count == 0
    assert sessions[0].closed is True
    assert sessions[0].events == ["commit", "close"]


@pytest.mark.anyio
async def test_transaction_middleware_propagates_marked_error_commit_failure(
    monkeypatch,
) -> None:
    commit_error = RuntimeError("commit failed")
    sessions = install_session_factory(monkeypatch, commit_error=commit_error)

    async def downstream(request: Request) -> Response:
        mark_transaction_commit_on_error(request)
        return Response(status_code=401)

    with pytest.raises(RuntimeError) as caught:
        await transaction_middleware(make_request(), downstream)

    assert caught.value is commit_error
    assert sessions[0].committed is False
    assert sessions[0].rollback_count == 1
    assert sessions[0].closed is True
    assert sessions[0].events == ["commit", "rollback", "close"]


@pytest.mark.anyio
async def test_transaction_middleware_propagates_unknown_integrity_error(
    monkeypatch,
) -> None:
    commit_error = IntegrityError(
        "INSERT INTO datasets ...",
        {},
        Exception("unrelated integrity violation"),
    )
    sessions = install_session_factory(monkeypatch, commit_error=commit_error)

    async def downstream(_: Request) -> Response:
        return Response("ok", status_code=201)

    with pytest.raises(IntegrityError) as caught:
        await transaction_middleware(make_request(), downstream)

    assert caught.value is commit_error
    assert len(sessions) == 1
    assert sessions[0].committed is False
    assert sessions[0].rollback_count == 1
    assert sessions[0].closed is True
    assert sessions[0].events == ["commit", "rollback", "close"]
