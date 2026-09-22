# Phase 1 PostgreSQL Setup

This slice adds PostgreSQL connectivity, async SQLAlchemy access, and an empty
Alembic migration workflow. It does not create application-domain tables.

## Configuration

Copy `.env.example` to `.env` for local use and replace the placeholder
password:

```text
POSTGRES_DB=dataforge
POSTGRES_USER=dataforge
POSTGRES_PASSWORD=<local-password>
POSTGRES_PORT=5432
DATAFORGE_DATABASE_URL=postgresql+asyncpg://dataforge:<local-password>@localhost:5432/dataforge
```

`.env` is ignored by Git and must not be committed.

## Start PostgreSQL

```powershell
docker compose up -d postgres
docker compose ps
```

Wait for the container health status to become `healthy`.

## Apply migrations

```powershell
alembic upgrade head
```

The initial migration set is intentionally empty. Domain tables will be added
in later slices.

## Run the application

```powershell
uvicorn app.main:app --reload
```

The health endpoints are:

```text
GET http://localhost:8000/api/v1/health/live
GET http://localhost:8000/api/v1/health/ready
```

Liveness does not access PostgreSQL. Readiness runs a lightweight `SELECT 1`
and reports `not_ready` when PostgreSQL is unavailable. The application still
starts when PostgreSQL is down.

## Run tests

```powershell
pip install -r requirements-dev.txt
pytest tests -q
```

The readiness success test requires a reachable PostgreSQL instance. The
failure and liveness tests use a mocked database check and do not require one.
