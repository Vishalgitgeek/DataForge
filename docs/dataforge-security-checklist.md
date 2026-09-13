# DataForge Security Checklist

## MVP required

### Authentication

- [ ] Hash passwords with Argon2id or bcrypt; never log or store plaintext.
- [ ] Enforce password length and reject common/compromised passwords where
      practical.
- [ ] Use short-lived access JWTs.
- [ ] Store only hashed refresh tokens; rotate and revoke on refresh/logout.
- [ ] Validate token issuer, audience, signature, expiry, and token type.
- [ ] Apply login rate limiting and avoid user-enumerating error messages.

### Authorization and API

- [ ] Require authentication on all dataset/version/result/query endpoints.
- [ ] Scope every database query through the authenticated user's ownership.
- [ ] Return a safe not-found response for inaccessible resource identifiers.
- [ ] Validate request bodies, path UUIDs, pagination, filters, sort, and limits.
- [ ] Use parameterized SQL and allow-listed columns/operators only.
- [ ] Set request, response, query-cost, and upload-size limits.
- [ ] Return stable error codes without stack traces or secrets.

### Files and object storage

- [ ] Accept only configured extensions and MIME types.
- [ ] Validate magic bytes/parser behavior, not just the filename.
- [ ] Generate object keys; never use user input as a filesystem path.
- [ ] Use short-lived presigned URLs scoped to one object and operation.
- [ ] Verify object size, checksum when available, and metadata before queuing.
- [ ] Keep raw files out of API local disks and source control.
- [ ] Define deletion and retention behavior for soft-deleted datasets.
- [ ] Treat uploaded files as untrusted input and isolate worker parsing.

### Database, queue, and worker

- [ ] Use least-privilege database credentials and TLS in deployed environments.
- [ ] Enforce foreign keys, unique constraints, and safe state transitions.
- [ ] Keep secrets out of logs, error details, and job payloads.
- [ ] Make handlers idempotent; acknowledge messages only after durable commit.
- [ ] Bound retries and inspect dead-letter messages.
- [ ] Validate job ownership/version state before processing.
- [ ] Prevent arbitrary SQL and unbounded analytical work.

### Secrets and operations

- [ ] Load secrets from environment/secret management, not committed files.
- [ ] Rotate JWT, database, broker, Redis, and object-storage credentials.
- [ ] Use separate credentials and buckets for local/test/production.
- [ ] Add correlation IDs and structured security-relevant audit logs.
- [ ] Do not log passwords, tokens, presigned URLs, or raw sensitive data.

## Post-MVP hardening

- [ ] Add TLS everywhere in production and secure cookie/token transport policy.
- [ ] Add dependency and container image scanning.
- [ ] Add malware scanning/quarantine for high-risk deployments.
- [ ] Add network policies/security groups and private service endpoints.
- [ ] Add centralized secret management and key-management integration.
- [ ] Add backup encryption, restore drills, and retention verification.
- [ ] Add WAF/API gateway protections and distributed rate limiting.
- [ ] Add formal threat modeling for upload, query, AI, and multi-tenant paths.
- [ ] Add OpenTelemetry access/audit tracing with privacy review.
- [ ] Review data deletion, export, and privacy obligations before launch.

## Security review gates

Before MVP release, test cross-user access, expired/revoked tokens, malformed
files, path traversal names, oversized uploads, SQL-injection-shaped filters,
raw SQL attempts, replayed job messages, leaked error details, and dependency
outages. Record findings by severity and remediate all critical/high findings.
