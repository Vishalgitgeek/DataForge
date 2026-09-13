# DataForge

## Production-Oriented Data Analysis & Intelligence Platform

**Version:** 1.0
**Project Type:** Backend-heavy software engineering project
**Primary Goal:** Backend engineering learning + portfolio + interview preparation

---

# 1. Project Vision

DataForge is a backend-heavy platform that allows users to upload business datasets and automatically transform raw data into structured, queryable and useful analytical information.

The platform should not be treated as a simple file-upload or CRUD application.

Its purpose is to provide a realistic environment in which the developer must solve backend engineering problems involving:

* large file handling
* asynchronous processing
* background workers
* message queues
* database design
* query optimization
* caching
* rate limiting
* concurrency
* idempotency
* failure recovery
* search
* analytical processing
* observability
* scalability
* cloud deployment

The final product should allow a user to go from:

**Raw dataset → processed dataset → data profile → analysis → insights → interactive querying**

without requiring the user to understand the underlying technical implementation.

---

# 2. Project Objectives

DataForge has two equally important objectives.

## 2.1 Product Objective

Build a useful platform where a user can:

1. Upload a dataset.
2. Track its processing status.
3. View automatically generated information about the dataset.
4. Identify data-quality problems.
5. Explore statistical and business-level analysis.
6. Search and filter the dataset.
7. Compare different versions of a dataset.
8. Ask analytical questions through an API.
9. Eventually ask questions using natural language.
10. Export analytical results.

---

## 2.2 Engineering/Learning Objective

The project must provide practical exposure to backend engineering concepts relevant to professional backend/SDE roles.

The developer should gain practical understanding of:

### Backend fundamentals

* REST API design
* request validation
* response design
* authentication
* authorization
* API versioning
* pagination
* filtering
* error handling

### Databases

* PostgreSQL
* relational modeling
* normalization
* constraints
* transactions
* isolation levels
* indexes
* composite indexes
* query optimization
* connection pooling
* `EXPLAIN ANALYZE`

### Distributed/asynchronous systems

* background jobs
* message brokers
* producers
* consumers
* worker processes
* retries
* dead-letter queues
* idempotency
* eventual consistency
* job state management

### Performance

* Redis
* caching
* cache invalidation
* rate limiting
* batching
* connection pooling
* large-file processing

### Concurrency

* race conditions
* atomic operations
* distributed locks
* duplicate jobs
* concurrent dataset processing

### Storage

* object storage
* presigned URLs
* large-file uploads
* file lifecycle management

### Infrastructure

* Docker
* Docker Compose
* AWS
* deployment
* health checks
* environment configuration

### Observability

* structured logging
* metrics
* latency
* error rates
* queue metrics
* cache hit ratio
* monitoring

### System design

* horizontal scaling
* stateless APIs
* worker scaling
* bottleneck identification
* failure handling
* capacity considerations

---

# 3. Product Philosophy

DataForge should follow five principles.

## 3.1 Computation must be deterministic

The system should calculate numerical/statistical results using trusted processing systems such as:

* PostgreSQL
* SQL
* Polars
* Pandas where appropriate
* DuckDB where appropriate

An LLM must not be responsible for calculating the underlying numerical truth.

---

## 3.2 AI should enhance the product, not replace the backend

AI may be used for:

* natural-language query interpretation
* generating explanations
* summarizing already-computed results
* identifying potentially interesting findings from structured analytical results

The architecture should be:

```text
Dataset
   ↓
Data Processing
   ↓
Deterministic Analysis
   ↓
Structured Results
   ↓
AI
   ↓
Natural-language Explanation
```

Not:

```text
Dataset
   ↓
LLM
   ↓
"Trust whatever it says"
```

---

## 3.3 Complexity must have a reason

A technology should only be introduced when the product has a problem that justifies it.

For example:

Redis should exist because caching/rate limiting is required.

RabbitMQ should exist because expensive processing must be decoupled from API requests.

Object storage should exist because large files should not live inside the application server.

Distributed locking should exist because concurrent operations create race conditions.

---

## 3.4 Start simple and evolve

The initial architecture should not use microservices merely to appear impressive.

Start with:

```text
                    React
                      |
                      v
              FastAPI Application
                      |
       +--------------+--------------+
       |              |              |
       v              v              v
 PostgreSQL         Redis       Object Storage
                      |
                      |
                  RabbitMQ
                      |
                      v
              Background Workers
```

The application should initially be a modular monolith.

If later measurements demonstrate that a component needs independent scaling or isolation, its separation can be considered.

---

## 3.5 Measure before optimizing

Performance improvements should be based on measurement.

The project should intentionally allow us to demonstrate situations such as:

```text
Before optimization
    ↓
Measure bottleneck
    ↓
Apply optimization
    ↓
Measure again
```

Examples:

* slow database query → add appropriate index
* repeated expensive computation → introduce caching
* blocked API request → move work to background worker
* excessive duplicate requests → rate limiting
* duplicate jobs → idempotency

---

# 4. Target Users

The initial target user is a non-technical or semi-technical user who receives a dataset and wants to understand it without manually writing analysis code.

Potential users include:

* business analysts
* operations teams
* students
* small businesses
* developers needing quick dataset profiling
* data teams performing initial data exploration

The project does not need to become a full enterprise BI platform.

The focus is on the analytical workflow and backend engineering.

---

# 5. Core User Journey

The primary workflow is:

```text
Register
   ↓
Login
   ↓
Create Dataset
   ↓
Upload File
   ↓
Processing Job Created
   ↓
Background Processing
   ↓
Schema Detection
   ↓
Data Profiling
   ↓
Quality Analysis
   ↓
Statistical Analysis
   ↓
Analysis Results Stored
   ↓
User Views Results
   ↓
User Queries Dataset
   ↓
Optional AI Explanation
```

---

# 6. Dataset Lifecycle

Every uploaded dataset should have a defined lifecycle.

```text
CREATED
   ↓
UPLOADING
   ↓
UPLOADED
   ↓
QUEUED
   ↓
PROCESSING
   ↓
COMPLETED
```

Failure states:

```text
PROCESSING
    ↓
FAILED
```

A failed job may be retried according to the retry policy.

The system must maintain enough information to determine:

* what happened
* when it happened
* why it failed
* whether it can be retried
* whether processing is already complete

---

# 7. Dataset Versioning

Dataset uploads should support versions.

Example:

```text
sales.csv

Version 1
1,000,000 rows

Version 2
1,150,000 rows

Version 3
1,300,000 rows
```

Each version should maintain its own:

* file
* schema
* profile
* quality results
* statistics
* processing status

This enables future comparison.

For example:

```text
Version 1 → Version 2

Rows:             +15%
Missing values:   -8%
New columns:      2
Removed columns:  0
Changed types:    1
```

Dataset versioning should therefore become a core product capability rather than a future afterthought.

---

# 8. Supported Input

## Initial formats

* CSV
* XLSX

## Future formats

Potentially:

* JSON
* Parquet
* PDF

PDF is explicitly not part of the initial analytical pipeline because PDF is fundamentally different from structured tabular data.

---

# 9. File Handling Architecture

Files should not be permanently stored inside the application server.

The intended architecture is:

```text
Client
   ↓
API
   ↓
Request upload authorization
   ↓
Object Storage
   ↓
File uploaded
   ↓
API notified
   ↓
Processing job created
```

Production storage:

**AWS S3**

Local development:

**MinIO or equivalent object-storage emulator**

The architecture should eventually support:

* file size validation
* content-type validation
* extension validation
* safe file naming
* metadata extraction
* file lifecycle management
* secure access
* deletion

---

# 10. Large Dataset Requirement

The system should not assume that every dataset fits comfortably into application memory.

The architecture should eventually support files significantly larger than the available RAM of a worker.

Example:

```text
Worker RAM: 4 GB

Dataset: 8 GB
```

The worker must not simply attempt:

```python
df = read_entire_file_into_memory()
```

Instead, appropriate strategies should be investigated:

* chunk processing
* streaming
* Polars
* DuckDB
* batch operations
* temporary storage
* incremental aggregation

The exact implementation should be determined during development based on actual workload characteristics.

---

# 11. Automatic Data Profiling

After ingestion, DataForge should automatically determine:

## Dataset-level information

* row count
* column count
* duplicate row count
* file size
* processing duration

## Column-level information

* column name
* inferred data type
* null count
* null percentage
* unique count
* uniqueness ratio
* sample values

## Numerical columns

Potential statistics:

* minimum
* maximum
* mean
* median
* standard deviation
* percentiles
* distribution
* potential outliers

## Categorical columns

Potential statistics:

* number of unique values
* most frequent values
* frequency distribution
* rare values

## Date/time columns

Potential statistics:

* minimum date
* maximum date
* distribution over time
* missing periods where appropriate

---

# 12. Data Quality Analysis

The platform should produce a data-quality assessment.

Possible checks:

```text
Missing values
Duplicate rows
Invalid types
Unexpected values
Extreme values
Constant columns
Highly unique columns
Potential outliers
```

Each dataset should receive a quality summary.

Example:

```text
Data Quality Score: 87/100

Missing Values       ⚠
Duplicates           ✓
Type Consistency     ✓
Outliers             ⚠
Empty Columns        ✓
```

The scoring methodology must be deterministic and documented.

---

# 13. Analytical Engine

Profiling alone is not enough.

DataForge should have an analytical layer capable of generating useful analytical results.

For suitable datasets, the system may calculate:

* aggregations
* grouped statistics
* trends
* distributions
* rankings
* top/bottom entities
* growth rates
* correlations
* outlier summaries

For example, for a sales dataset:

```text
Total Revenue
Average Order Value
Revenue by City
Revenue by Product
Monthly Revenue
Top Products
Top Customers
Growth Rate
```

The system should not assume every dataset is a sales dataset.

The analysis planner should determine which analyses are meaningful based on detected column types and available fields.

---

# 14. Analysis Planner

A major backend component should eventually be an **Analysis Planner**.

Its responsibility is to determine what analytical operations are appropriate for a dataset.

Example:

```text
Dataset Schema

price       → numerical
quantity    → numerical
city        → categorical
product     → categorical
order_date  → datetime
```

The planner may determine:

```text
Numerical analysis
Categorical analysis
Time-series analysis
Correlation analysis
Outlier analysis
```

It then creates appropriate analysis jobs.

Conceptually:

```text
Dataset
   ↓
Schema Detector
   ↓
Analysis Planner
   ↓
Analysis Jobs
   ├── Statistics
   ├── Quality
   ├── Distribution
   ├── Correlation
   └── Time Series
```

---

# 15. Asynchronous Processing

Dataset processing must not block the HTTP request.

Instead:

```text
POST /datasets
       ↓
Create Dataset
       ↓
Create Processing Job
       ↓
Publish Message
       ↓
Return Job ID
```

Then:

```text
RabbitMQ
    ↓
Worker
    ↓
Process Dataset
    ↓
Store Results
    ↓
Update Job Status
```

The API should return quickly while expensive processing happens asynchronously.

---

# 16. Job Management

Every significant background operation should have a job representation.

A job should track information such as:

* job ID
* dataset/version ID
* job type
* status
* attempt count
* created time
* started time
* completed time
* failure information

Potential states:

```text
PENDING
RUNNING
COMPLETED
FAILED
RETRYING
CANCELLED
```

This allows the frontend/API to expose processing progress without coupling the user request to the processing duration.

---

# 17. Retry and Failure Handling

Workers will occasionally fail.

Examples:

* malformed file
* temporary database failure
* worker crash
* object-storage timeout
* message broker interruption

The system should distinguish between:

### Retryable errors

Example:

```text
temporary network failure
database temporarily unavailable
```

and:

### Non-retryable errors

Example:

```text
corrupted file
unsupported file format
invalid dataset
```

Retry behavior should be explicitly designed.

Repeated failures should eventually be moved to a dead-letter or failed-job state.

---

# 18. Idempotency

Background processing must be designed so that the same job cannot accidentally produce duplicate results.

Example:

```text
Message delivered
      ↓
Worker processes
      ↓
Worker crashes before acknowledgement
      ↓
Message delivered again
```

The system must safely handle this scenario.

Possible mechanisms include:

* job state validation
* unique constraints
* idempotency keys
* deterministic job identifiers
* transactional result creation

The final implementation should be chosen after studying the trade-offs.

---

# 19. Concurrency

The project should intentionally address concurrent operations.

Examples:

### Duplicate analysis requests

```text
User clicks "Analyze"
User clicks again immediately
```

### Concurrent workers

```text
Worker A → Dataset 123
Worker B → Dataset 123
```

### Concurrent dataset version creation

The system must prevent invalid state transitions and duplicate resources.

This provides practical exposure to:

* race conditions
* transactions
* locking
* atomic operations
* unique constraints
* distributed locks where necessary

---

# 20. Redis

Redis should serve multiple practical purposes where justified.

Potential uses:

### Caching

Cache expensive analytical results.

```text
API
 ↓
Redis
 ↓ cache hit
return

cache miss
 ↓
Database / analytical engine
 ↓
Redis
 ↓
return
```

### Rate limiting

Protect expensive APIs.

Example:

```text
100 analytical requests / minute / user
```

### Distributed coordination

If required by the architecture, Redis may be used for distributed locks or other coordination mechanisms.

Redis must not automatically become the primary source of truth.

---

# 21. Rate Limiting

Not every API should have unlimited access.

Particularly expensive endpoints should have rate limits.

Examples:

```text
Dataset upload
Analysis request
Natural-language query
Export generation
```

Rate limiting should eventually be implemented using Redis.

The implementation should explore different strategies such as:

* fixed window
* sliding window
* token bucket

and select an appropriate strategy based on project requirements.

---

# 22. Analytical Query API

Users should eventually be able to query their dataset programmatically.

Example:

```http
POST /api/v1/datasets/{dataset_id}/query
```

Request:

```json
{
  "dimensions": ["city"],
  "metrics": ["revenue"],
  "filters": {
    "year": 2026
  },
  "sort": "-revenue",
  "limit": 10
}
```

The backend should convert the request into a safe analytical operation.

The system must prevent:

* arbitrary SQL execution
* SQL injection
* unauthorized dataset access
* unbounded expensive queries

---

# 23. Natural-Language Querying

Natural-language querying is an important advanced feature.

Example:

> "Which city generated the most revenue this year?"

The architecture should be:

```text
User Question
      ↓
LLM
      ↓
Structured Query Representation
      ↓
Backend Validation
      ↓
Query Engine
      ↓
Database / Analytical Engine
      ↓
Result
      ↓
LLM Explanation
```

The LLM should not directly execute arbitrary SQL against the database.

The backend must validate the generated query representation before execution.

---

# 24. Search

Search may be introduced where it solves a genuine product problem.

Potential search capabilities:

* dataset search
* column search
* textual dataset values
* metadata search

Elasticsearch/OpenSearch should only be introduced if PostgreSQL search becomes insufficient for the intended use case.

The project should first understand PostgreSQL's search capabilities before introducing a separate search engine.

---

# 25. Caching Strategy

Caching should not be added blindly.

Potential cache candidates:

```text
Dataset profile
Column statistics
Frequently requested aggregations
Dashboard data
```

Each cached item should have:

* cache key
* TTL
* invalidation strategy

The system should explicitly handle:

```text
Cache hit
Cache miss
Expired cache
Cache invalidation
Redis unavailable
```

---

# 26. Database Design

The database should evolve toward a model similar to:

```text
User
 │
 └── Dataset
       │
       ├── DatasetVersion
       │      │
       │      ├── DatasetFile
       │      ├── DatasetColumn
       │      │       └── ColumnStatistics
       │      │
       │      ├── DataQualityResult
       │      ├── AnalysisResult
       │      └── ProcessingJob
       │
       └── QueryHistory
```

Additional entities may be introduced only when justified by requirements.

Important database concepts should include:

* UUIDs
* foreign keys
* constraints
* indexes
* composite indexes
* transactions
* timestamps
* status enums
* unique constraints

---

# 27. Query Optimization

The project must include deliberate database-performance exercises.

For selected endpoints:

1. Implement a straightforward query.
2. Measure performance.
3. Inspect the query plan.
4. Identify bottlenecks.
5. Introduce appropriate indexes or query changes.
6. Measure again.

Example:

```text
Before:
p95 = 420ms

After:
p95 = 65ms
```

Actual numbers must come from benchmarks rather than being invented.

---

# 28. API Design

The API should follow consistent REST principles.

Example:

```text
POST   /api/v1/auth/register
POST   /api/v1/auth/login

GET    /api/v1/datasets
POST   /api/v1/datasets

GET    /api/v1/datasets/{id}
DELETE /api/v1/datasets/{id}

GET    /api/v1/datasets/{id}/versions
POST   /api/v1/datasets/{id}/versions

GET    /api/v1/datasets/{id}/profile
GET    /api/v1/datasets/{id}/analysis

POST   /api/v1/datasets/{id}/query
```

The exact API structure may evolve as the system design becomes clearer.

---

# 29. Authentication and Authorization

Initial authentication should support:

* registration
* login
* logout
* password hashing
* access tokens
* refresh tokens
* protected endpoints

Authorization must ensure that a user cannot access another user's datasets.

Example:

```text
User A
  ↓
GET Dataset A → allowed

User A
  ↓
GET Dataset B owned by User B → forbidden
```

The project should distinguish clearly between:

**Authentication: Who are you?**

and

**Authorization: What are you allowed to access?**

---

# 30. Security Requirements

The system should consider:

* password hashing
* secure token handling
* input validation
* authorization checks
* SQL injection prevention
* file validation
* path traversal prevention
* malicious file handling
* request size limits
* rate limiting
* secrets management
* secure object-storage access

Security should be considered during implementation rather than added at the end.

---

# 31. Observability

The production version should provide visibility into system behavior.

Track:

### API

* request count
* response latency
* error rate
* status codes

### Workers

* jobs processed
* failed jobs
* retry count
* processing duration

### Queue

* queue depth
* waiting jobs
* processing rate

### Database

* query latency
* connection usage

### Cache

* hit ratio
* miss ratio
* memory usage

The initial implementation may use structured logging, followed by metrics and monitoring.

Potential tools:

* Prometheus
* Grafana
* OpenTelemetry

---

# 32. Testing Strategy

The project should not rely only on manual testing.

Testing should include:

### Unit tests

For:

* data profiling
* statistics
* validation
* business logic

### Integration tests

For:

* PostgreSQL
* Redis
* object storage
* message broker

### API tests

For:

* authentication
* authorization
* dataset endpoints
* query endpoints

### Failure tests

For:

* malformed files
* worker failure
* duplicate jobs
* unavailable dependencies
* invalid requests

### Performance testing

For selected endpoints and processing workflows.

---

# 33. Docker

The development environment should be reproducible.

Local infrastructure should eventually include containers for:

```text
FastAPI
PostgreSQL
Redis
RabbitMQ
Worker
MinIO
```

Additional services should only be introduced when required.

Docker Compose should be used for local orchestration.

---

# 34. Deployment

The production deployment should eventually run on AWS.

A possible architecture:

```text
                   Internet
                      │
                      ▼
                Load Balancer
                      │
             ┌────────┴────────┐
             ▼                 ▼
          API #1             API #2
             │                 │
             └────────┬────────┘
                      │
              PostgreSQL
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
          Redis                S3
            │
            ▼
        Message Broker
            │
       ┌────┴────┐
       ▼         ▼
   Worker #1  Worker #2
```

The architecture should be able to scale API instances independently from processing workers.

The exact AWS services should be chosen based on the requirements and learning objectives rather than assumed beforehand.

---

# 35. MVP

The MVP should be deliberately smaller than the final system.

## MVP includes

### Authentication

* registration
* login
* JWT authentication
* authorization

### Dataset

* CSV upload
* dataset metadata
* dataset history
* dataset version

### Processing

* basic schema detection
* row/column counts
* missing values
* unique values
* numerical statistics

### Architecture

* PostgreSQL
* object storage
* background worker
* RabbitMQ

### Frontend

A minimal React interface for:

* login
* upload
* processing status
* dataset list
* dataset profile

The MVP should already demonstrate asynchronous processing.

---

# 36. Post-MVP Development

After the MVP is stable:

## Stage 1 — Data Quality

Add:

* duplicate detection
* outlier detection
* quality score
* additional column analysis

## Stage 2 — Performance

Add:

* Redis caching
* database indexes
* query optimization
* rate limiting

## Stage 3 — Reliability

Add:

* retry policies
* dead-letter handling
* idempotency
* failure recovery
* concurrency controls

## Stage 4 — Analytics

Add:

* analytical query API
* grouped aggregations
* trends
* comparisons
* dataset version comparison

## Stage 5 — Search

Evaluate PostgreSQL search first.

Introduce Elasticsearch/OpenSearch only if justified.

## Stage 6 — AI

Add:

* natural-language query interpretation
* structured query generation
* insight summaries
* analytical explanations

## Stage 7 — Production

Add:

* Docker production setup
* AWS deployment
* structured logging
* metrics
* monitoring
* performance benchmarks

---

# 37. Development Phases

## Phase 0 — Architecture & Design

Learn:

* requirements
* system design
* modular architecture
* database modeling
* API design

Deliverables:

* architecture document
* ER diagram
* API specification
* development plan

---

## Phase 1 — Backend Foundation

Build:

* FastAPI
* configuration
* PostgreSQL
* Alembic
* health endpoint
* basic project structure
* Docker

Learn:

* application structure
* dependency injection
* migrations
* environment configuration
* containerization

---

## Phase 2 — Authentication

Build:

* registration
* login
* access tokens
* refresh tokens
* protected routes
* authorization

Learn:

* authentication
* authorization
* JWT
* password security

---

## Phase 3 — Dataset Management

Build:

* datasets
* versions
* metadata
* ownership
* CRUD operations

Learn:

* relational modeling
* foreign keys
* constraints
* transactions
* query design

---

## Phase 4 — Object Storage & Uploads

Build:

* file upload
* object storage
* file metadata
* validation
* secure access

Learn:

* object storage
* presigned URLs
* large-file handling
* upload security

---

## Phase 5 — Data Profiling

Build:

* schema detection
* column profiling
* statistics
* quality checks

Learn:

* data processing
* computational complexity
* memory management
* analytical computation

---

## Phase 6 — Asynchronous Architecture

Build:

* RabbitMQ
* worker
* processing jobs
* job states
* retries
* failure handling

Learn:

* asynchronous processing
* message queues
* producers/consumers
* worker architecture
* eventual consistency

---

## Phase 7 — Reliability

Build:

* idempotency
* duplicate-job protection
* dead-letter handling
* retry policies
* safe state transitions

Learn:

* fault tolerance
* idempotency
* failure recovery
* distributed systems

---

## Phase 8 — Performance

Build:

* Redis caching
* rate limiting
* database indexes
* query optimization
* connection pooling

Learn:

* caching
* cache invalidation
* rate limiting
* database performance
* benchmarking

---

## Phase 9 — Analytical Query Engine

Build:

* filtering
* grouping
* aggregations
* sorting
* analytical query API

Learn:

* query engines
* dynamic query construction
* query safety
* analytical databases

---

## Phase 10 — Concurrency

Introduce controlled concurrency problems and solve them using:

* database constraints
* transactions
* locks
* Redis where appropriate

Learn:

* race conditions
* atomicity
* locking
* concurrent requests

---

## Phase 11 — AI Layer

Build:

* natural-language questions
* structured query generation
* backend validation
* deterministic execution
* natural-language explanation

Learn:

* LLM integration
* structured outputs
* AI safety boundaries
* AI + traditional backend architecture

---

## Phase 12 — Observability

Build:

* structured logs
* metrics
* monitoring
* worker metrics
* API metrics

Learn:

* observability
* production debugging
* performance monitoring

---

## Phase 13 — Deployment

Build:

* production Docker configuration
* AWS deployment
* scalable API
* scalable workers
* health checks

Learn:

* cloud deployment
* horizontal scaling
* infrastructure
* production operations

---

# 38. Engineering Experiments

The project should contain deliberate experiments rather than only feature development.

Examples:

## Experiment 1 — Synchronous vs asynchronous processing

Measure:

```text
API response time
CPU utilization
worker utilization
user experience
```

---

## Experiment 2 — Database optimization

Compare:

```text
Query without index
        vs
Query with appropriate index
```

Use query plans and benchmarks.

---

## Experiment 3 — Cache performance

Compare:

```text
PostgreSQL query
        vs
Redis cache hit
```

Measure latency.

---

## Experiment 4 — Duplicate job handling

Simulate:

```text
Same job delivered twice
```

Verify that results remain correct.

---

## Experiment 5 — Worker failure

Kill a worker during processing.

Verify:

```text
Job recovery
Retry
State consistency
No duplicate result
```

---

## Experiment 6 — Concurrent requests

Send multiple requests for the same expensive operation.

Measure and solve the resulting race condition or duplicate work.

These experiments should become part of the project's technical documentation.

---

# 39. Interview Preparation

For every major component, maintain interview notes.

Examples:

### PostgreSQL

* Why PostgreSQL?
* What is an index?
* Why composite indexes?
* What is a transaction?
* What are isolation levels?
* How does connection pooling work?
* How do you diagnose a slow query?

### Redis

* Why Redis?
* Cache-aside vs write-through?
* How does TTL work?
* What happens if Redis goes down?
* How do you handle stale cache?

### RabbitMQ

* Why use a message broker?
* What happens if a worker crashes?
* What happens if a message is delivered twice?
* What are acknowledgements?
* How do retries work?
* What is a dead-letter queue?

### Large files

* How would you process a 10 GB file?
* Why can't you load everything into memory?
* How does chunk processing work?

### Scaling

* How would you handle 10x traffic?
* How would you scale workers?
* What becomes the bottleneck?
* How would you handle database load?

### AI

* Why shouldn't the LLM directly execute SQL?
* How do you validate an LLM-generated query?
* How do you prevent hallucinated analytical results?

---

# 40. Definition of Success

DataForge should be considered successful only when the developer can explain both:

## Product

> "What does DataForge do and why would someone use it?"

and:

## Engineering

> "Why does every major architectural component exist, how does it work, what can fail, and how would I scale it?"

The final project should allow the developer to confidently explain:

```text
Request lifecycle
Database architecture
File lifecycle
Processing lifecycle
Queue lifecycle
Worker failure
Retry behavior
Caching strategy
Query optimization
Concurrency handling
Security
Scaling strategy
Observability
AI integration
```

---

# 41. Final Architecture Goal

The architecture should evolve toward:

```text
                         ┌──────────────┐
                         │    React     │
                         └──────┬───────┘
                                │
                              HTTPS
                                │
                                ▼
                     ┌────────────────────┐
                     │      FastAPI       │
                     │   Modular Monolith │
                     └─────────┬──────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
       PostgreSQL           Redis          Object Storage
             │                 │                 │
             │                 │                 │
             └─────────────────┼─────────────────┘
                               │
                         Message Broker
                            RabbitMQ
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
                 ▼             ▼             ▼
             Ingestion     Profiling     Analytics
              Worker        Worker         Worker
                 │             │             │
                 └─────────────┼─────────────┘
                               │
                               ▼
                       Analysis Results
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
              Query Engine           AI Layer
                    │                     │
                    └──────────┬──────────┘
                               ▼
                          User Insights
```

This is the **target architecture, not the architecture we build on day one**.

The system should evolve into this architecture as requirements demand it.

---

# 42. Explicit Non-Goals

DataForge is NOT intended to become:

* a complete Tableau replacement
* a complete Power BI replacement
* a general-purpose ETL platform
* a full machine-learning platform
* a generic chatbot
* a collection of unrelated backend technologies
* a microservices showcase

The project should remain focused on:

**Data ingestion + processing + analysis + backend engineering.**

---

# 43. Guiding Principle

The most important rule for the entire project is:

> **Do not build features merely to demonstrate technologies. Build realistic features that create engineering problems, then use appropriate technologies to solve those problems.**

The project should therefore demonstrate not:

> "I know Redis, RabbitMQ, Docker and AWS."

but:

> **"I encountered a problem, evaluated possible solutions, selected an architecture, implemented it, measured the result, handled its failure modes, and understand why the system works."**

That is the primary learning and portfolio objective of DataForge.
