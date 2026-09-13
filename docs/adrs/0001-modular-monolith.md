# ADR 0001: Start with a Modular Monolith

- Status: Accepted
- Date: 2026-09-13

## Context

DataForge needs authentication, dataset management, storage orchestration,
processing, analytics, and API delivery. The PRD explicitly says not to use
microservices merely to demonstrate technology.

## Decision

Build one FastAPI deployable application with explicit internal modules and a
separately runnable worker process. Preserve module interfaces and domain
events so independently scaling or extracting a component remains possible.

## Alternatives considered

- Microservices from day one: rejected due to unnecessary operational and
  distributed-system complexity before scaling evidence exists.
- One unstructured application module: rejected because it creates coupling and
  makes future extraction and testing difficult.

## Consequences

The initial deployment is simpler and faster to test. API and worker can still
scale independently. Module boundaries must be enforced by code review and
tests; extraction is deferred until measurements justify it.
