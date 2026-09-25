from app.models import Base


def test_core_domain_schema_metadata_is_registered() -> None:
    expected_tables = {
        "users",
        "refresh_tokens",
        "datasets",
        "dataset_versions",
        "dataset_files",
        "dataset_columns",
        "column_statistics",
        "profiles",
        "quality_results",
        "analysis_runs",
        "analysis_results",
        "processing_jobs",
        "query_history",
    }

    tables = set(Base.metadata.tables)

    assert expected_tables.issubset(tables)
