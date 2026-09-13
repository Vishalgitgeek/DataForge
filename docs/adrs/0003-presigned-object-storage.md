# ADR 0003: Store Files in Object Storage with Presigned Uploads

- Status: Accepted
- Date: 2026-09-13

## Context

Uploaded datasets can be large and must not consume application-server disk or
memory. The PRD names S3 for production and MinIO for local development.

## Decision

Store raw files in S3-compatible object storage. The API creates a generated
object key and a short-lived presigned upload URL. The client uploads directly;
the API verifies object metadata before creating a processing job.

## Alternatives considered

- Multipart upload through FastAPI: rejected as an unnecessary API bottleneck.
- PostgreSQL large objects: rejected because object storage better fits large
  immutable files and lifecycle management.

## Consequences

API instances remain stateless and large transfers bypass them. Upload
completion must be idempotent, storage credentials need careful scoping, and
orphaned objects require cleanup.
