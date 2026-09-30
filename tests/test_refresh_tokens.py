import hashlib
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.dml import Update

from app.core.errors import AuthenticationError, RefreshTokenReuseError
from app.core.refresh_tokens import generate_refresh_token, hash_refresh_token
from app.models import RefreshToken
from app.schemas.auth import AuthResponse
from app.services.refresh_tokens import (
    REFRESH_TOKEN_LIFETIME,
    create_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)


def test_generated_refresh_tokens_have_256_bits_of_random_entropy(monkeypatch) -> None:
    entropy = secrets.token_bytes(32)
    requested_sizes: list[int] = []

    def token_bytes(size: int) -> bytes:
        requested_sizes.append(size)
        return entropy

    monkeypatch.setattr(secrets, "token_bytes", token_bytes)

    token = generate_refresh_token()
    decoded = urlsafe_b64decode(token + "=" * (-len(token) % 4))

    assert len(decoded) == 32
    assert requested_sizes == [32]
    assert len(token) >= 43
    assert token == urlsafe_b64encode(entropy).rstrip(b"=").decode("ascii")


def test_generated_refresh_tokens_differ() -> None:
    assert generate_refresh_token() != generate_refresh_token()


def test_refresh_token_hash_is_deterministic_sha256() -> None:
    raw_token = generate_refresh_token()

    assert hash_refresh_token(raw_token) == hash_refresh_token(raw_token)
    assert hash_refresh_token(raw_token) == hashlib.sha256(
        raw_token.encode("ascii")
    ).hexdigest()
    assert hash_refresh_token(raw_token) != raw_token


@pytest.mark.anyio
async def test_create_refresh_token_persists_only_hash_and_uses_family_expiry() -> None:
    user_id = uuid4()
    family_id = uuid4()
    created_at = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    added: list[object] = []
    events: list[str] = []

    class FakeSession:
        def add(self, instance: object) -> None:
            added.append(instance)
            events.append("add")

        async def flush(self) -> None:
            events.append("flush")

        async def commit(self) -> None:
            events.append("commit")

        async def rollback(self) -> None:
            events.append("rollback")

    raw_token, row = await create_refresh_token(
        FakeSession(),
        user_id,
        family_id,
        now=created_at,
    )

    assert isinstance(row, RefreshToken)
    assert added == [row]
    assert row.user_id == user_id
    assert row.family_id == family_id
    assert row.token_hash == hash_refresh_token(raw_token)
    assert row.token_hash != raw_token
    assert row.created_at == created_at
    assert row.expires_at == created_at + timedelta(days=30)
    assert REFRESH_TOKEN_LIFETIME == timedelta(days=30)
    assert events == ["add", "flush"]


@pytest.mark.anyio
async def test_rotate_refresh_token_revokes_and_replaces_in_same_family(
    monkeypatch,
) -> None:
    now = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    user_id = uuid4()
    family_id = uuid4()
    current = RefreshToken(
        id=uuid4(),
        user_id=user_id,
        family_id=family_id,
        token_hash=hash_refresh_token("presented-token"),
        expires_at=now + timedelta(days=2),
        revoked_at=None,
        created_at=now - timedelta(days=1),
    )
    added: list[RefreshToken] = []
    statements = []
    events: list[str] = []

    class Result:
        def scalar_one_or_none(self):
            return current

    class FakeSession:
        async def execute(self, statement):
            statements.append(statement)
            events.append("select_for_update")
            return Result()

        def add(self, instance: RefreshToken) -> None:
            added.append(instance)
            events.append("add")

        async def flush(self) -> None:
            events.append("flush")

        async def commit(self) -> None:
            events.append("commit")

        async def rollback(self) -> None:
            events.append("rollback")

    monkeypatch.setattr(
        "app.services.refresh_tokens.generate_refresh_token",
        lambda: "replacement-token",
    )
    monkeypatch.setattr(
        "app.services.refresh_tokens.get_settings",
        lambda: type("SettingsStub", (), {"access_token_lifetime_seconds": 900})(),
    )
    monkeypatch.setattr(
        "app.services.refresh_tokens.create_access_token",
        lambda token_user_id: f"access-{token_user_id}",
    )

    response = await rotate_refresh_token(
        FakeSession(),
        "presented-token",
        now=now,
    )

    assert isinstance(response, AuthResponse)
    assert response.access_token == f"access-{user_id}"
    assert response.refresh_token == "replacement-token"
    assert response.token_type == "bearer"
    assert response.expires_in == 900
    assert current.revoked_at == now
    assert len(added) == 1
    replacement = added[0]
    assert replacement.user_id == user_id
    assert replacement.family_id == family_id
    assert replacement.token_hash == hash_refresh_token("replacement-token")
    assert replacement.token_hash != "replacement-token"
    assert replacement.revoked_at is None
    assert replacement.expires_at == now + timedelta(days=30)
    assert statements[0]._for_update_arg is not None
    assert "FOR UPDATE" in str(
        statements[0].compile(dialect=postgresql.dialect())
    )
    assert events == ["select_for_update", "add", "flush"]


@pytest.mark.anyio
async def test_reused_refresh_token_revokes_only_active_tokens_in_its_family() -> None:
    now = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    family_id = uuid4()
    other_family_id = uuid4()
    presented = RefreshToken(
        id=uuid4(),
        user_id=uuid4(),
        family_id=family_id,
        token_hash=hash_refresh_token("presented-token"),
        expires_at=now + timedelta(days=5),
        revoked_at=now - timedelta(minutes=1),
        created_at=now - timedelta(days=1),
    )
    active_same_family = RefreshToken(
        id=uuid4(),
        user_id=presented.user_id,
        family_id=family_id,
        token_hash=hash_refresh_token("active-family-token"),
        expires_at=now + timedelta(days=10),
        revoked_at=None,
        created_at=now,
    )
    active_other_family = RefreshToken(
        id=uuid4(),
        user_id=presented.user_id,
        family_id=other_family_id,
        token_hash=hash_refresh_token("other-family-token"),
        expires_at=now + timedelta(days=10),
        revoked_at=None,
        created_at=now,
    )
    rows = [presented, active_same_family, active_other_family]
    statements = []

    class Result:
        def scalar_one_or_none(self):
            return presented

    class FakeSession:
        async def execute(self, statement):
            statements.append(statement)
            if isinstance(statement, Update):
                for row in rows:
                    if row.family_id == family_id and row.revoked_at is None:
                        row.revoked_at = now
                return None
            return Result()

    with pytest.raises(RefreshTokenReuseError) as caught:
        await rotate_refresh_token(
            FakeSession(),
            "presented-token",
            now=now,
        )

    assert isinstance(caught.value, AuthenticationError)
    assert len(statements) == 2
    update_sql = str(statements[1].compile(dialect=postgresql.dialect()))
    assert "family_id" in update_sql
    assert "revoked_at IS NULL" in update_sql
    assert active_same_family.revoked_at == now
    assert active_other_family.revoked_at is None
    assert presented.revoked_at == now - timedelta(minutes=1)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("revoked_at", "expires_at", "error_type"),
    [
        (datetime(2026, 9, 30, tzinfo=UTC), datetime(2026, 10, 2, tzinfo=UTC), "auth"),
        (None, datetime(2026, 9, 30, tzinfo=UTC), "expired"),
    ],
)
async def test_rotate_refresh_token_rejects_revoked_or_expired_token(
    revoked_at,
    expires_at,
    error_type: str,
) -> None:
    now = datetime(2026, 10, 1, tzinfo=UTC)
    current = RefreshToken(
        id=uuid4(),
        user_id=uuid4(),
        family_id=uuid4(),
        token_hash=hash_refresh_token("presented-token"),
        expires_at=expires_at,
        revoked_at=revoked_at,
        created_at=now - timedelta(days=1),
    )

    class Result:
        def scalar_one_or_none(self):
            return current

    statements = []

    class FakeSession:
        async def execute(self, statement):
            statements.append(statement)
            return Result()

    from app.core.errors import RefreshTokenExpiredError

    expected_error = (
        RefreshTokenExpiredError
        if error_type == "expired"
        else RefreshTokenReuseError
    )
    with pytest.raises(expected_error):
        await rotate_refresh_token(
            FakeSession(),
            "presented-token",
            now=now,
        )
    assert len(statements) == (2 if revoked_at is not None else 1)


@pytest.mark.anyio
async def test_rotate_refresh_token_rejects_unknown_and_malformed_values() -> None:
    class Result:
        def scalar_one_or_none(self):
            return None

    class FakeSession:
        async def execute(self, _statement):
            return Result()

    from app.core.errors import AuthenticationError

    for raw_token in ("unknown-token", "not-ascii-\N{SNOWMAN}"):
        with pytest.raises(AuthenticationError):
            await rotate_refresh_token(
                FakeSession(),
                raw_token,
                now=datetime(2026, 10, 1, tzinfo=UTC),
            )


@pytest.mark.anyio
@pytest.mark.parametrize("token_state", ["active", "revoked", "missing"])
async def test_logout_revokes_only_matching_active_token_idempotently(
    token_state: str,
) -> None:
    now = datetime(2026, 10, 1, tzinfo=UTC)
    family_id = uuid4()
    presented_hash = hash_refresh_token("presented-token")
    presented = (
        RefreshToken(
            id=uuid4(),
            user_id=uuid4(),
            family_id=family_id,
            token_hash=presented_hash,
            expires_at=now + timedelta(days=10),
            revoked_at=(
                now - timedelta(hours=1) if token_state == "revoked" else None
            ),
            created_at=now - timedelta(days=1),
        )
        if token_state != "missing"
        else None
    )
    same_family = RefreshToken(
        id=uuid4(),
        user_id=uuid4(),
        family_id=family_id,
        token_hash=hash_refresh_token("same-family-token"),
        expires_at=now + timedelta(days=10),
        revoked_at=None,
        created_at=now,
    )
    other_family = RefreshToken(
        id=uuid4(),
        user_id=uuid4(),
        family_id=uuid4(),
        token_hash=hash_refresh_token("other-family-token"),
        expires_at=now + timedelta(days=10),
        revoked_at=None,
        created_at=now,
    )
    rows = [row for row in (presented, same_family, other_family) if row is not None]
    statements = []

    class FakeSession:
        async def execute(self, statement):
            statements.append(statement)
            if isinstance(statement, Update):
                if token_state == "active" and presented is not None:
                    presented.revoked_at = now

    await revoke_refresh_token(
        FakeSession(),
        "presented-token",
        now=now,
    )

    assert len(statements) == (1 if token_state != "missing" else 1)
    compiled = str(statements[0].compile(dialect=postgresql.dialect()))
    assert "token_hash" in compiled
    assert "revoked_at IS NULL" in compiled
    assert "family_id" not in compiled
    if token_state == "active":
        assert presented is not None and presented.revoked_at == now
    elif token_state == "revoked":
        assert presented is not None
        assert presented.revoked_at == now - timedelta(hours=1)
    else:
        assert presented is None
    assert same_family.revoked_at is None
    assert other_family.revoked_at is None
    assert len(rows) == (3 if presented is not None else 2)
