# DataForge Error Model

## Error envelope

All JSON errors use the same shape:

```json
{
  "error": {
    "code": "version_not_ready",
    "message": "The requested profile is not available yet.",
    "details": {
      "version_id": "00000000-0000-0000-0000-000000000000",
      "status": "PROCESSING"
    },
    "retryable": true
  },
  "request_id": "req_01J..."
}
```

`message` is safe for end users. `details` contains structured, non-secret
diagnostics. Stack traces, SQL, object-storage credentials, and internal
paths are never returned. `request_id` is also written to structured logs and
is returned as the `X-Request-ID` response header.

Clients may send an `X-Request-ID` request header. If omitted, the API
generates one. The effective value is returned on every response, included in
API logs, and propagated into any RabbitMQ message and worker logs created by
that request. `Idempotency-Key` remains a separate header for deduplicating
mutating commands; it is not a correlation ID.

## Error taxonomy

| Code | HTTP | Retry policy | Client action |
|---|---:|:---:|---|
| `validation_error` | 422 | No | Correct request fields |
| `unsupported_file_type` | 415 | Never | Upload MVP-supported CSV |
| `file_too_large` | 413 | No | Reduce or split the file |
| `authentication_required` | 401 | No | Authenticate |
| `invalid_credentials` | 401 | No | Re-enter credentials |
| `token_expired` | 401 | No | Refresh or log in again |
| `forbidden` | 403 | No | Use an authorized resource |
| `resource_not_found` | 404 | No | Verify the identifier |
| `conflict` | 409 | Never automatically | Refresh state and retry intentionally |
| `invalid_state_transition` | 409 | Never | Follow the current lifecycle |
| `version_not_ready` | 409 | Retry after status changes | Poll status, then retry |
| `query_rejected` | 422 | Never | Reduce cost or correct fields |
| `rate_limited` | 429 | Retry after `Retry-After` | Wait for the indicated interval |
| `storage_unavailable` | 503 | Retry with bounded backoff | Retry the request |
| `database_unavailable` | 503 | Retry with bounded backoff | Retry the request |
| `queue_unavailable` | 503 | Retry with bounded backoff | Retry submission |
| `processing_failed_permanent` | 422 | Never automatically | Fix the input or inspect durable job failure |
| `processing_retry_exhausted` | 503 | No automatic retry; explicit version retry only | Inspect status and request an explicit retry |
| `internal_error` | 500 | Never automatically | Report request ID; do not blind-loop |

The API may use a generic `resource_not_found` response for resources not
owned by the caller to avoid leaking whether another user's identifier exists.

## Processing failure categories

### Non-retryable

- malformed or corrupted file
- unsupported format
- invalid headers or inconsistent schema
- file fails configured safety validation
- query references nonexistent columns

### Retryable

- temporary database connection failure
- object-storage timeout
- broker interruption
- transient worker dependency failure

Retryable worker failures are bounded by `max_attempts` and exponential
backoff. A permanent worker failure is exposed as
`processing_failed_permanent` when an API response must describe it. A
retryable failure that reaches the attempt limit is exposed as
`processing_retry_exhausted`; the worker job is durably `FAILED` and the
message is routed for dead-letter inspection. Neither code triggers an
automatic client retry. An authorized user may explicitly request a new
version retry as documented in the lifecycle artifact.

## HTTP behavior

- Validation errors identify field paths in `details`.
- `202 Accepted` indicates a command was accepted but processing is incomplete.
- `409` is used for valid resources in an incompatible state.
- `429` includes `Retry-After`.
- `503` indicates a dependency or service availability problem and should
  include a safe retry hint.
- Error responses preserve the correlation/request ID.
