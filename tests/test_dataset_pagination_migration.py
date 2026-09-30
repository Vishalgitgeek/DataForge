import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "a31f74e8c205_add_active_dataset_listing_index.py"
)
SPEC = importlib.util.spec_from_file_location(
    "active_dataset_listing_index_migration",
    MIGRATION_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def test_upgrade_creates_active_dataset_owner_ordering_index(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        MIGRATION.op,
        "create_index",
        lambda *args, **kwargs: calls.append(("create_index", *args, kwargs)),
    )

    MIGRATION.upgrade()

    assert calls[0][1] == "ix_datasets_active_owner_created_id"
    assert calls[0][2] == "datasets"
    assert calls[0][3][0] == "owner_id"
    assert str(calls[0][3][1]) == "created_at DESC"
    assert str(calls[0][3][2]) == "id DESC"
    assert calls[0][4]["unique"] is False
    assert str(calls[0][4]["postgresql_where"]) == "deleted_at IS NULL"


def test_downgrade_drops_active_dataset_owner_ordering_index(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        MIGRATION.op,
        "drop_index",
        lambda *args, **kwargs: calls.append(("drop_index", *args, kwargs)),
    )

    MIGRATION.downgrade()

    assert calls[0][1] == "ix_datasets_active_owner_created_id"
    assert calls[0][2]["table_name"] == "datasets"
    assert str(calls[0][2]["postgresql_where"]) == "deleted_at IS NULL"
