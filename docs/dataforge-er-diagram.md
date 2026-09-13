# DataForge ER Diagram

## PostgreSQL entity model

```mermaid
erDiagram
    USERS ||--o{ REFRESH_TOKENS : owns
    USERS ||--o{ DATASETS : owns
    USERS ||--o{ QUERY_HISTORY : submits
    DATASETS ||--o{ DATASET_VERSIONS : contains
    DATASET_VERSIONS ||--|| DATASET_FILES : stores
    DATASET_VERSIONS ||--o{ DATASET_COLUMNS : defines
    DATASET_COLUMNS ||--|| COLUMN_STATISTICS : summarizes
    DATASET_VERSIONS ||--|| PROFILES : has
    DATASET_VERSIONS ||--o{ QUALITY_RESULTS : assesses
    DATASET_VERSIONS ||--o{ ANALYSIS_RUNS : plans
    ANALYSIS_RUNS ||--|| ANALYSIS_RESULTS : produces
    DATASET_VERSIONS ||--o{ PROCESSING_JOBS : processes
    DATASET_VERSIONS ||--o{ QUERY_HISTORY : queries

    USERS {
        uuid id PK
        citext email UK
        text password_hash
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }
    REFRESH_TOKENS {
        uuid id PK
        uuid user_id FK
        text token_hash UK
        timestamptz expires_at
        timestamptz revoked_at
        timestamptz created_at
    }
    DATASETS {
        uuid id PK
        uuid owner_id FK
        text name
        text description
        timestamptz deleted_at
        timestamptz created_at
        timestamptz updated_at
    }
    DATASET_VERSIONS {
        uuid id PK
        uuid dataset_id FK
        int version_number
        dataset_version_status status
        bigint row_count
        int column_count
        text failure_code
        timestamptz created_at
        timestamptz updated_at
    }
    DATASET_FILES {
        uuid id PK
        uuid version_id FK_UK
        text storage_provider
        text bucket
        text object_key UK
        text original_filename
        text content_type
        bigint byte_size
        char checksum_sha256
        timestamptz uploaded_at
    }
    DATASET_COLUMNS {
        uuid id PK
        uuid version_id FK
        int ordinal
        text source_name
        text normalized_name
        column_type inferred_type
        boolean nullable
    }
    COLUMN_STATISTICS {
        uuid id PK
        uuid column_id FK_UK
        bigint null_count
        numeric null_fraction
        bigint unique_count
        numeric uniqueness_ratio
        jsonb sample_values
        jsonb numeric_summary
        jsonb categorical_summary
        jsonb datetime_summary
        timestamptz computed_at
    }
    PROFILES {
        uuid id PK
        uuid version_id FK_UK
        bigint duplicate_row_count
        bigint file_size_bytes
        bigint processing_duration_ms
        jsonb profile_payload
        timestamptz computed_at
    }
    QUALITY_RESULTS {
        uuid id PK
        uuid version_id FK
        text check_type
        quality_status status
        numeric score
        bigint affected_rows
        jsonb details
        timestamptz computed_at
    }
    ANALYSIS_RUNS {
        uuid id PK
        uuid version_id FK
        text analysis_type
        analysis_status status
        text input_fingerprint
        timestamptz created_at
        timestamptz completed_at
    }
    ANALYSIS_RESULTS {
        uuid id PK
        uuid run_id FK_UK
        jsonb result_payload
        timestamptz created_at
    }
    PROCESSING_JOBS {
        uuid id PK
        uuid version_id FK
        text job_type
        job_status status
        int attempt_count
        int max_attempts
        text idempotency_key
        boolean retryable
        text failure_code
        timestamptz queued_at
        timestamptz completed_at
    }
    QUERY_HISTORY {
        uuid id PK
        uuid user_id FK
        uuid version_id FK
        jsonb request_payload
        char normalized_query_hash
        query_status status
        int duration_ms
        text error_code
        timestamptz created_at
    }
```

## Boundary notes

- PostgreSQL is the source of truth for ownership, metadata, status, jobs, and
  analytical results.
- `DATASET_FILES.object_key` points to S3/MinIO; the file bytes are not stored
  in PostgreSQL.
- Redis contains cache/rate-limit/coordination state only.
- RabbitMQ contains delivery state only; durable job state remains in
  `PROCESSING_JOBS`.
- Every dataset/version read is scoped through `DATASETS.owner_id`.
- Version-specific results are isolated by `DATASET_VERSIONS.id`; a new upload
  never overwrites an earlier version's profile or analysis.
