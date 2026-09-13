# ADR 0006: Use Streaming and Chunked Processing for MVP CSV Files

- Status: Accepted
- Date: 2026-09-13

## Context

The MVP accepts CSV files and must support datasets larger than a worker's
available RAM. DataForge needs schema detection, row/column counts, null and
unique counts, and basic numerical statistics without loading an entire file
into memory. The PRD also requires the architecture to remain open to XLSX,
JSON, Parquet, and other future formats.

## Decision

Treat CSV as the only MVP input format. Process it through a streaming or
chunked reader with bounded memory. The ingestion module will:

1. validate the object and CSV structure before publishing processing results;
2. inspect a bounded sample for initial schema detection;
3. process the file in chunks/streams to compute incremental counts,
   aggregates, and statistics;
4. persist schema and results transactionally only after successful processing;
5. classify malformed, corrupted, or unsupported CSV input as a permanent
   processing failure, while temporary storage/database/worker failures remain
   retryable.

The ADR intentionally does not mandate Pandas, Polars, DuckDB, or another
specific implementation. That choice will be made and measured against actual
file sizes, column types, throughput, memory use, and correctness needs.

The processing interface is format-independent: an input adapter supplies
validated records/chunks and metadata to shared schema, profiling, quality,
and analysis services. XLSX and other formats can add adapters after the MVP
without redesigning upload orchestration, job state, or result storage.

## Alternatives considered

- Read the entire CSV into memory: rejected because files may exceed worker
  RAM and memory use would scale with file size.
- Mandate Pandas, Polars, or DuckDB now: rejected because the PRD requires
  measurement before optimizing and the workload has not yet been benchmarked.
- Process synchronously in the API: rejected because parsing is expensive and
  must not block HTTP requests.
- Make CSV-specific behavior the platform contract: rejected because it would
  make later format adapters unnecessarily invasive.

## Consequences

The MVP can process large CSV inputs with predictable memory bounds, but
incremental statistics and duplicate detection require deliberate algorithms
and may trade precision or temporary storage for memory usage. Malformed CSVs
fail deterministically without automatic retry; transient infrastructure
failures use the existing bounded worker retry policy. Benchmark results will
determine the concrete reader/analytical engine and any later optimization.
