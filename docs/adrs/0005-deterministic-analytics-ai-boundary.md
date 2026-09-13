# ADR 0005: Keep Numerical Analytics Deterministic and Bound AI

- Status: Accepted
- Date: 2026-09-13

## Context

Users may eventually ask natural-language questions, but analytical results
must be trustworthy and reproducible. The PRD prohibits relying on an LLM for
numerical truth or allowing arbitrary SQL execution.

## Decision

Compute statistics, quality scores, and query results using validated
deterministic operations in PostgreSQL and/or approved analytical libraries.
An AI adapter may produce a structured query representation or explain stored
results. The backend validates every generated representation before execution,
and records the request and result metadata.

## Alternatives considered

- Let the LLM generate and execute SQL directly: rejected due to injection,
  authorization, cost, and hallucination risks.
- Use AI for all profiling: rejected because results would be non-deterministic
  and difficult to test.

## Consequences

The analytical engine owns correctness and safety. AI integration is more
constrained, but explanations can be added without weakening data integrity or
tenant isolation.
