# ADR 0004: Use RabbitMQ for Asynchronous Processing

- Status: Accepted
- Date: 2026-09-13

## Context

Parsing, profiling, quality checks, and analysis can be slow, memory-intensive,
and failure-prone. HTTP requests must return without waiting for processing.

## Decision

Persist a processing job in PostgreSQL, publish an idempotent message to
RabbitMQ, and process it in a worker. A worker acknowledges only after durable
result/state commit. Retryable failures use bounded backoff; exhausted
messages are recorded as failed and routed to dead-letter handling.

## Alternatives considered

- Synchronous API processing: rejected because it blocks requests and makes
  failure recovery and scaling harder.
- Redis queue: rejected because RabbitMQ's acknowledgement, routing, and
  dead-letter semantics directly fit the workflow.

## Consequences

The system gains responsiveness and independently scalable workers, but must
handle eventual consistency, duplicate delivery, retries, stale jobs, and
broker observability.
