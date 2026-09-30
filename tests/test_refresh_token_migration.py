import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "d7a4f9c2b681_add_refresh_token_family_id.py"
)
SPEC = importlib.util.spec_from_file_location(
    "refresh_token_family_migration",
    MIGRATION_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def test_upgrade_backfills_existing_tokens_as_single_token_families(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        MIGRATION.op,
        "add_column",
        lambda *args: calls.append(("add", *args)),
    )
    monkeypatch.setattr(
        MIGRATION.op,
        "execute",
        lambda *args: calls.append(("execute", *args)),
    )
    monkeypatch.setattr(
        MIGRATION.op,
        "alter_column",
        lambda *args, **kwargs: calls.append(("alter", *args, kwargs)),
    )
    monkeypatch.setattr(
        MIGRATION.op,
        "create_index",
        lambda *args, **kwargs: calls.append(("index", *args, kwargs)),
    )

    MIGRATION.upgrade()

    assert calls[0][0] == "add"
    assert calls[0][2].name == "family_id"
    assert calls[0][2].nullable is True
    assert calls[1] == (
        "execute",
        "UPDATE refresh_tokens SET family_id = id WHERE family_id IS NULL",
    )
    assert calls[2] == ("alter", "refresh_tokens", "family_id", {"nullable": False})
    assert calls[3][0] == "index"
    assert calls[3][1] == "ix_refresh_tokens_family_revoked"
    assert calls[3][3] == ["family_id", "revoked_at"]


def test_downgrade_removes_only_family_index_and_column(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        MIGRATION.op,
        "drop_index",
        lambda *args, **kwargs: calls.append(("drop_index", *args, kwargs)),
    )
    monkeypatch.setattr(
        MIGRATION.op,
        "drop_column",
        lambda *args: calls.append(("drop_column", *args)),
    )

    MIGRATION.downgrade()

    assert calls == [
        (
            "drop_index",
            "ix_refresh_tokens_family_revoked",
            {"table_name": "refresh_tokens"},
        ),
        ("drop_column", "refresh_tokens", "family_id"),
    ]
