# DataForge Database Design

## 1. Storage responsibilities

| Concern | System |
|---|---|
| Users, ownership, lifecycle, jobs, metadata, results, history | PostgreSQL |
| Raw CSV/XLSX and optional generated artifacts | S3/MinIO |
| Cache, rate-limit counters, short-lived locks | Redis |
| Work delivery and retry/dead-letter routing | RabbitMQ |

PostgreSQL is authoritative. Redis and RabbitMQ data can be rebuilt or
replayed.

## 2. Entity relationship model

```text
users
  1 ───< datasets
             1 ───< dataset_versions
                         1 ───  dataset_files
                         1 ───< dataset_columns
                                      1 ───  column_statistics
                         1 ───  profiles
                         1 ───< quality_results
                         1 ───< analysis_results
                         1 ───< processing_jobs
users 1 ───< refresh_tokens
users 1 ───< query_history >───1 dataset_versions
dataset_versions 1 ───< analysis_runs
```

## 3. Tables

### `users`

- `id uuid primary key`
- `email citext not null unique`
- `password_hash text not null`
- `is_active boolean not null default true`
- `created_at`, `updated_at timestamptz not null`

### `refresh_tokens`

- `id uuid primary key`
- `user_id uuid not null references users(id)`
- `token_hash text not null unique`
- `expires_at timestamptz not null`
- `revoked_at timestamptz null`
- `created_at timestamptz not null`

Index `(user_id, revoked_at, expires_at)`.

### `datasets`

Represents the logical dataset owned by a user.

- `id uuid primary key`
- `owner_id uuid not null references users(id)`
- `name text not null`
- `description text null`
- `created_at`, `updated_at`, `deleted_at timestamptz`

Unique active name per owner can be enforced with a partial unique index on
`(owner_id, lower(name)) where deleted_at is null`.

### `dataset_versions`

- `id uuid primary key`
- `dataset_id uuid not null references datasets(id)`
- `version_number integer not null check (version_number > 0)`
- `status dataset_version_status not null`
- `row_count bigint null check (row_count >= 0)`
- `column_count integer null check (column_count >= 0)`
- `processing_started_at`, `processing_completed_at timestamptz`
- `failure_code`, `failure_message text null`
- `created_at`, `updated_at timestamptz not null`

Unique `(dataset_id, version_number)`. Index `(dataset_id, created_at desc)`.
Use a transaction/row lock when allocating the next version number.

### `dataset_files`

- `id uuid primary key`
- `version_id uuid not null unique references dataset_versions(id)`
- `storage_provider text not null`
- `bucket text not null`
- `object_key text not null unique`
- `original_filename text not null`
- `content_type text not null`
- `file_extension text not null`
- `byte_size bigint not null check (byte_size >= 0)`
- `checksum_sha256 char(64) null`
- `uploaded_at timestamptz`
- `created_at timestamptz not null`

### `dataset_columns`

- `id uuid primary key`
- `version_id uuid not null references dataset_versions(id)`
- `ordinal integer not null check (ordinal >= 0)`
- `source_name text not null`
- `normalized_name text not null`
- `inferred_type column_type not null`
- `nullable boolean not null`
- `created_at timestamptz not null`

Unique `(version_id, ordinal)` and `(version_id, normalized_name)`.

### `column_statistics`

One current deterministic statistics record per column.

- `id uuid primary key`
- `column_id uuid not null unique references dataset_columns(id)`
- `null_count bigint not null`
- `null_fraction numeric(8,7) not null check (null_fraction between 0 and 1)`
- `unique_count bigint null`
- `uniqueness_ratio numeric(8,7) null`
- `sample_values jsonb not null default '[]'`
- `numeric_summary jsonb null`
- `categorical_summary jsonb null`
- `datetime_summary jsonb null`
- `computed_at timestamptz not null`

JSONB stores variable-shaped summaries while the high-value query dimensions
remain relational.

### `profiles`

- `id uuid primary key`
- `version_id uuid not null unique references dataset_versions(id)`
- `duplicate_row_count bigint not null default 0`
- `file_size_bytes bigint not null`
- `processing_duration_ms bigint null`
- `profile_payload jsonb not null`
- `computed_at timestamptz not null`

### `quality_results`

- `id uuid primary key`
- `version_id uuid not null references dataset_versions(id)`
- `check_type text not null`
- `status quality_status not null`
- `score numeric(5,2) null`
- `affected_rows bigint null`
- `details jsonb not null default '{}'`
- `computed_at timestamptz not null`

Unique `(version_id, check_type, computed_at)` for audit history; a view or
`is_current` flag can expose the latest run.

### `analysis_runs` and `analysis_results`

`analysis_runs` tracks a planned execution:

- `id uuid primary key`
- `version_id uuid not null references dataset_versions(id)`
- `analysis_type text not null`
- `status analysis_status not null`
- `input_fingerprint text not null`
- `created_at`, `completed_at timestamptz`

Unique `(version_id, analysis_type, input_fingerprint)`.

`analysis_results` stores the output:

- `id uuid primary key`
- `run_id uuid not null unique references analysis_runs(id)`
- `result_payload jsonb not null`
- `created_at timestamptz not null`

### `processing_jobs`

- `id uuid primary key`
- `version_id uuid not null references dataset_versions(id)`
- `job_type text not null`
- `status job_status not null`
- `attempt_count integer not null default 0`
- `max_attempts integer not null`
- `idempotency_key text not null`
- `retryable boolean null`
- `failure_code`, `failure_message text null`
- `queued_at`, `started_at`, `completed_at`, `updated_at timestamptz`

Unique `(version_id, job_type, idempotency_key)`. Partial unique index for one
non-terminal job per `(version_id, job_type)`.

### `query_history`

- `id uuid primary key`
- `user_id uuid not null references users(id)`
- `version_id uuid not null references dataset_versions(id)`
- `request_payload jsonb not null`
- `normalized_query_hash char(64) not null`
- `result_metadata jsonb null`
- `status query_status not null`
- `duration_ms integer null`
- `error_code text null`
- `created_at timestamptz not null`

Indexes `(user_id, created_at desc)` and `(version_id, created_at desc)`.

## 4. Enum values and constraints

- `dataset_version_status`: `CREATED`, `UPLOADING`, `UPLOADED`, `QUEUED`,
  `PROCESSING`, `COMPLETED`, `FAILED`
- `job_status`: `PENDING`, `RUNNING`, `RETRYING`, `COMPLETED`, `FAILED`,
  `CANCELLED`
- `column_type`: `INTEGER`, `DECIMAL`, `BOOLEAN`, `DATETIME`, `TEXT`,
  `UNKNOWN`
- `quality_status`: `PASS`, `WARN`, `FAIL`
- `query_status`: `SUCCEEDED`, `REJECTED`, `FAILED`

Application-level transition rules must be backed by conditional updates and
transactions; database enums alone do not enforce valid transitions.

## 5. Indexing and transaction plan

Start with ownership and lifecycle indexes, then validate additions with
`EXPLAIN ANALYZE`:

- datasets: `(owner_id, updated_at desc)`
- versions: `(dataset_id, created_at desc)` and `(status, updated_at)`
- jobs: `(status, queued_at)` for claiming
- columns: `(version_id, ordinal)` and unique normalized name
- query history: `(user_id, created_at desc)`

Use transactions for upload completion + job creation, version allocation,
job claiming, result persistence + completion transition, and refresh-token
rotation. Use `READ COMMITTED` initially; introduce stronger isolation only
for a measured anomaly.

## 6. Data retention and migrations

Use Alembic migrations. Soft-delete logical datasets first, retain audit/job
history, and delete object-storage files asynchronously after retention
policy approval. Every migration must be backward-compatible with the running
worker/API during deployment.
