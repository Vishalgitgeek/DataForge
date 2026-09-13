# DataForge Development Plan

## 1. Delivery strategy

Build the smallest end-to-end asynchronous product first, then add reliability,
performance, analytics, AI, and production operations. Each phase has a
demonstrable outcome and a validation gate. Do not add a technology until the
corresponding problem is observable.

## 2. MVP definition

MVP includes:

- Registration, login, JWT access/refresh tokens, logout, ownership checks.
- Dataset metadata, CSV upload through MinIO/S3, and version history.
- Version lifecycle and one asynchronous processing job.
- Schema detection, row/column counts, missing values, unique counts, and
  basic numerical statistics.
- PostgreSQL, RabbitMQ, object storage, one worker, Docker Compose.
- React screens for login, upload, dataset list, status, and profile.

MVP excludes XLSX, AI, OpenSearch, advanced comparisons, and production AWS
deployment until the core lifecycle is stable.

## 3. Phased plan

### Phase 0 - Architecture and contracts

Deliver architecture, ERD, API contract, lifecycle diagrams, error model,
security checklist, and a decision record for CSV processing. Define
non-functional baselines: maximum upload size, API latency target, worker
concurrency, retry count, and retention assumptions.

**Gate:** every MVP workflow has an owner, API shape, state transitions, and
failure behavior.

### Phase 1 - Backend foundation

Create FastAPI modular structure, configuration validation, SQLAlchemy,
Alembic, PostgreSQL migrations, health/readiness endpoints, structured logging,
and Docker Compose. Add repository/service boundaries and test fixtures.

**Gate:** clean startup, migration from empty database, readiness checks, and
one API integration test.

### Phase 2 - Authentication

Implement user registration, password hashing, login, access JWTs, refresh-token
rotation/revocation, logout, protected dependencies, and ownership policy.
Test invalid credentials, expired/revoked tokens, and cross-user access.

**Gate:** no dataset route can return another user's resource.

### Phase 3 - Dataset and version management

Implement dataset CRUD, version allocation under concurrency, lifecycle
transitions, pagination, and metadata endpoints. Add constraints and
transaction tests.

**Gate:** concurrent version creation produces no duplicate version numbers.

### Phase 4 - Upload and object storage

Add MinIO locally and S3-compatible storage interfaces. Implement presigned
upload, upload-complete verification, file metadata, content/extension/size
validation, safe object keys, and deletion workflow.

**Gate:** raw files never enter API local storage and incomplete uploads cannot
be processed.

### Phase 5 - Profiling pipeline

Implement RabbitMQ publishing, one worker consumer, CSV parser, schema
detection, chunked processing, deterministic profile/statistics, and result
persistence. Use fixtures for empty, malformed, wide, duplicate, null-heavy,
and numeric datasets.

**Gate:** API returns quickly with a job ID; completed profiles are repeatable
and correct without loading the whole file into memory.

### Phase 6 - Reliability

Add explicit job state transitions, conditional job claiming, idempotency keys,
bounded exponential retries, retryable/non-retryable error categories,
dead-letter routing, stale-job recovery, and duplicate-message tests.

**Gate:** replaying a message or killing a worker does not duplicate results or
leave an unexplainable state.

### Phase 7 - Quality analysis

Add duplicate rows, type consistency, missing values, constant/high-cardinality
columns, outlier summaries, deterministic quality rules, and documented
0-100 scoring. Expose check-level details and a summary endpoint.

**Gate:** the same input and rule version produce the same score.

### Phase 8 - Performance and protection

Measure baseline endpoints and worker throughput. Add indexes only after
`EXPLAIN ANALYZE`; add Redis cache-aside for version-keyed profile/analysis,
rate limits for uploads and expensive queries, connection pooling, and cache
invalidation.

**Gate:** benchmark reports show measured before/after results and Redis outage
behavior is explicit.

### Phase 9 - Analytical query engine

Define a typed query schema for dimensions, metrics, filters, sort, and limit.
Implement allow-listed parameterized SQL/Polars/DuckDB execution, query
timeouts/cost limits, query history, grouped aggregations, trends, rankings,
and version comparison.

**Gate:** arbitrary SQL, unauthorized versions, unbounded limits, and invalid
column/type combinations are rejected.

### Phase 10 - Concurrency and scale exercises

Test concurrent analysis requests, duplicate clicks, concurrent workers,
cache stampedes, and simultaneous version creation. Use constraints,
transactions, row locks, and Redis locks only where necessary. Document the
observed bottleneck and selected remedy.

**Gate:** load tests demonstrate correctness under contention, not merely
successful single-request behavior.

### Phase 11 - AI layer

Add an adapter that converts natural-language questions into a validated
structured query. Validate datasets, columns, operators, limits, and cost
before deterministic execution. Add explanations and summaries based only on
stored results, with prompt/version/audit metadata.

**Gate:** an LLM cannot execute arbitrary SQL or invent numeric results.

### Phase 12 - Observability and deployment

Add metrics, traces where useful, dashboards, worker/queue alerts, production
Docker images, backups, migrations in deployment, AWS object storage, managed
PostgreSQL/Redis/broker, load-balanced stateless API instances, and separately
scaled workers.

**Gate:** operators can trace a request through upload, job, worker, results,
and query; health checks and rollback procedures are documented.

## 4. Initial API surface

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout

GET  /api/v1/datasets
POST /api/v1/datasets
GET  /api/v1/datasets/{dataset_id}
DELETE /api/v1/datasets/{dataset_id}

GET  /api/v1/datasets/{dataset_id}/versions
POST /api/v1/datasets/{dataset_id}/versions
POST /api/v1/versions/{version_id}/upload
POST /api/v1/versions/{version_id}/upload-complete
POST /api/v1/versions/{version_id}/retry
GET  /api/v1/versions/{version_id}/status
GET  /api/v1/versions/{version_id}/profile
GET  /api/v1/versions/{version_id}/quality
GET  /api/v1/versions/{version_id}/analysis
POST /api/v1/versions/{version_id}/query
GET  /api/v1/versions/{version_id}/query-history
```

Return `202` for accepted asynchronous commands, cursor pagination for lists,
stable error codes, and correlation IDs in responses.

## 5. Test and validation matrix

- Unit: parsers, schema inference, statistics, quality rules, scoring, query
  validation, state transitions.
- Integration: PostgreSQL/Alembic, MinIO, RabbitMQ, Redis, worker handlers.
- API: auth, ownership, upload lifecycle, status, profile, query rejection.
- Failure: malformed files, timeouts, worker crash, duplicate delivery,
  unavailable dependencies, stale jobs, invalid transitions.
- Performance: upload authorization, list/profile endpoints, query endpoint,
  queue throughput, memory usage on files larger than worker RAM.

## 6. Engineering experiments

1. Synchronous versus asynchronous processing: API latency and worker load.
2. Query/index optimization: plan and measured latency before and after.
3. PostgreSQL versus Redis cache hit latency and invalidation behavior.
4. Duplicate message delivery and idempotent result creation.
5. Worker termination during processing and recovery behavior.
6. Concurrent expensive requests and lock/constraint effectiveness.

Record workload, environment, measurements, conclusion, and follow-up in
technical decision notes; never publish invented benchmark numbers.

## 7. Definition of done for the first release

- A user can register, upload a CSV, watch asynchronous status, and view a
  deterministic profile.
- A second upload creates an isolated version with isolated results.
- Unauthorized users receive the same safe not-found/forbidden policy
  consistently.
- Malformed and oversized files fail with actionable, persisted diagnostics.
- Duplicate messages and worker retries are safe.
- Tests cover the happy path and required failure modes.
- Local setup is reproducible with Docker Compose and migrations.
