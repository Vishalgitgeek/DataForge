# ADR 0002: Use PostgreSQL as the System of Record

- Status: Accepted
- Date: 2026-09-13

## Context

DataForge needs durable ownership, versioning, lifecycle, job, profile, quality,
analysis, and query-history data with constraints and transactions.

## Decision

Use PostgreSQL as the authoritative store for metadata, state, and structured
results. Use UUIDs, foreign keys, unique constraints, indexes, and Alembic
migrations. Redis and RabbitMQ are supporting systems, not sources of truth.

## Alternatives considered

- Document database: rejected because the core model has strong relationships,
  ownership boundaries, and transactional state transitions.
- Redis as primary state: rejected because cache loss must not lose product data.

## Consequences

Relational constraints and query plans support correctness and deliberate
optimization. Variable-shaped summaries use JSONB while frequently filtered
ownership/lifecycle fields remain relational.
