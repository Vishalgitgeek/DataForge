import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "b6c8e2a41d73_add_dataset_version_listing_index.py"
)
SPEC = importlib.util.spec_from_file_location(
    "dataset_version_listing_index_migration",
    MIGRATION_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def test_upgrade_creates_dataset_version_listing_index(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        MIGRATION.op,
        "create_index",
        lambda *args, **kwargs: calls.append(("create_index", *args, kwargs)),
    )

    MIGRATION.upgrade()

    assert calls[0][1] == "ix_dataset_versions_dataset_created_id"
    assert calls[0][2] == "dataset_versions"
    assert calls[0][3][0] == "dataset_id"
    assert str(calls[0][3][1]) == "created_at DESC"
    assert str(calls[0][3][2]) == "id DESC"
    assert calls[0][4]["unique"] is False


def test_downgrade_drops_dataset_version_listing_index(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        MIGRATION.op,
        "drop_index",
        lambda *args, **kwargs: calls.append(("drop_index", *args, kwargs)),
    )

    MIGRATION.downgrade()

    assert calls == [
        (
            "drop_index",
            "ix_dataset_versions_dataset_created_id",
            {"table_name": "dataset_versions"},
        )
    ]
