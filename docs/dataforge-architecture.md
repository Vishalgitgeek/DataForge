# DataForge Architecture

## 1. Scope and design decisions

This design is derived from the DataForge PRD. It optimizes for a useful MVP and
for learning production backend engineering without introducing microservices
prematurely.

### Decisions

- Start with a modular monolith, not independently deployed microservices.
- Keep the API stateless and move expensive work to background workers.
- Keep PostgreSQL as the source of truth for metadata, job state, and results.
- Keep raw files and generated artifacts in object storage, never on API disks.
- Use RabbitMQ for durable work delivery and Redis only for cache, rate limits,
  and coordination where measurement justifies it.
- Calculate numerical results with deterministic code (SQL, Polars, Pandas, or
  DuckDB); AI may interpret or explain structured results but never supplies
  the numerical truth.

## 2. Target architecture

```text
React client
    |
 HTTPS / JSON
    v
FastAPI modular monolith
    |-- Auth and authorization
    |-- Dataset and version management
    |-- Upload orchestration
    |-- Profile, quality, and analysis APIs
    |-- Safe analytical query API
    |-- Optional AI adapter
    |
    +--> PostgreSQL (system of record)
    +--> Redis (cache, rate limits, short-lived locks)
    +--> S3/MinIO (raw files and artifacts)
    +--> RabbitMQ (processing messages)
                 |
                 v
          Background worker process
            |-- ingestion/schema detection
            |-- profiling/statistics
            |-- quality checks
            |-- analysis planner/execution
```

The worker can initially be one deployable process with separate modules and
queues. It can later be split into ingestion, profiling, and analytics workers
when metrics show independent scaling or isolation is needed.

## 3. Module boundaries

```text
app/
  api/             HTTP routes, dependencies, pagination, error mapping
  auth/            users, password hashing, JWT access/refresh tokens
  datasets/        dataset ownership, versions, lifecycle transitions
  storage/         presigned uploads, object keys, validation, deletion
  jobs/            job state machine, retry policy, idempotency
  processing/      parsers, schema detection, chunking, profiling
  quality/         deterministic quality rules and scoring
  analytics/       planner, safe query AST, aggregations, comparisons
  ai/              structured-query and explanation adapters
  persistence/     SQLAlchemy models, repositories, transactions
  infrastructure/  PostgreSQL, Redis, RabbitMQ, object-storage clients
  observability/   structured logs, metrics, tracing hooks
worker/
  consumers/       RabbitMQ consumers and acknowledgement policy
  tasks/           ingestion/profile/quality/analysis task handlers
```

Modules communicate through service interfaces and domain events rather than
directly importing route handlers. This preserves a future extraction seam.

## 4. Core request and processing flows

### Upload

1. Authenticated user creates a dataset or requests a new version.
2. API validates filename, extension, content type, size, and ownership.
3. API creates a `dataset_version` in `CREATED` and returns a presigned upload
   URL for S3/MinIO.
4. Client uploads directly to object storage.
5. Client calls upload-complete, or storage notification triggers the same
   idempotent command.
6. API verifies object existence and metadata, marks the version `UPLOADED`,
   creates a processing job, and publishes a message.
7. API returns `202 Accepted` with version and job identifiers.

The API accepts an optional `X-Request-ID` header and generates one when it is
omitted. It returns the effective value on every response. The ID is included
in structured API logs and propagated into the processing message and worker
logs. `Idempotency-Key` is separate and is used only to deduplicate commands.

### Worker

1. Consumer receives a message and atomically claims the job.
2. Worker reads the object as a stream/chunks; it must not assume the file fits
   in RAM.
3. Worker detects schema and persists columns.
4. Worker computes profile, statistics, quality checks, and planned analyses.
5. Results are committed transactionally and the version is marked `COMPLETED`.
6. The message is acknowledged only after the commit.
7. Retryable failures are requeued with bounded exponential backoff. Permanent
   failures become `FAILED`; exhausted retries are also recorded for dead-letter
   inspection.

An authorized dataset owner initiates an explicit retry with
`POST /api/v1/versions/{version_id}/retry` and a required `Idempotency-Key`.
The failed job remains an immutable `FAILED` record; the API creates one new
processing job and moves the version `FAILED -> QUEUED`. Repeating the same
idempotency key returns the original retry result. Concurrent retry requests
for the same version resolve to one active job through the database uniqueness
constraint; no additional retry lifecycle is introduced.

### Query

The query API accepts a typed, bounded JSON representation (dimensions,
metrics, filters, sort, limit), resolves columns by ID/name, validates types
and ownership, builds parameterized SQL/analytical-engine operations, enforces
limits and timeouts, stores query history, and returns structured results.
Arbitrary SQL is never accepted from users or passed through from an LLM.

## 5. State and reliability rules

Dataset version lifecycle:

```text
CREATED -> UPLOADING -> UPLOADED -> QUEUED -> PROCESSING -> COMPLETED
                                           \-> FAILED
```

Job lifecycle:

```text
PENDING -> RUNNING -> COMPLETED
             |          ^
             v          |
          RETRYING -----+
             |
             v
           FAILED / CANCELLED
```

- State transitions are allow-listed and executed in transactions.
- A unique active-job constraint prevents duplicate processing for one version.
- Workers claim jobs with row locking or an atomic conditional update.
- Result rows use unique keys based on version and analysis identity.
- Retryability is explicit, not inferred from an exception string.
- Replayed messages are safe because handlers are idempotent.

## 6. Security

- Argon2id or bcrypt password hashing; never store plaintext passwords.
- Short-lived access JWTs and revocable, rotated refresh tokens.
- Every dataset/version query scopes by authenticated owner.
- Presigned URLs are short-lived and scoped to a generated object key.
- Validate extension, MIME signature, size, and parser behavior; use generated
  object keys to prevent traversal and collisions.
- Parameterized queries and allow-listed query operators prevent SQL injection.
- Apply request-body, upload, query-cost, and per-user rate limits.
- Store secrets in environment/secret management, not source control.

## 7. Caching and rate limiting

Use cache-aside only for immutable or version-keyed results:

```text
profile:{version_id}:{result_version}
analysis:{version_id}:{analysis_hash}
query:{version_id}:{normalized_query_hash}
```

Set an explicit TTL and invalidate keys when a version's results are replaced.
Redis outage must degrade to PostgreSQL, except endpoints that require a
distributed limit/lock should return a clear temporary-unavailable response.

## 8. Observability and operations

Every request and job log should include correlation ID, user ID (when known),
dataset/version ID, job ID, duration, outcome, and error category.

Initial metrics:

- API request count, latency, status/error rate
- queue depth, job age, processing duration, retries, failures
- database pool usage and slow-query samples
- cache hits, misses, evictions, and memory

Health endpoints distinguish liveness from readiness and check required
dependencies. Add Prometheus/OpenTelemetry/Grafana after structured logging
and baseline measurements exist.

## 9. Deployment evolution

Local Docker Compose: FastAPI, worker, PostgreSQL, Redis, RabbitMQ, and MinIO.
Production can map these to AWS-managed equivalents (load balancer and
stateless API instances, managed PostgreSQL/Redis/RabbitMQ, S3, and separately
scalable workers). Exact AWS services should follow measured needs.

## 10. Explicit non-goals

Do not build a BI-suite replacement, generic ETL platform, ML platform,
standalone chatbot, or microservices showcase. Search, OpenSearch, and
specialized analytical storage are introduced only after PostgreSQL and the
initial analytical engine are measured and shown insufficient.
