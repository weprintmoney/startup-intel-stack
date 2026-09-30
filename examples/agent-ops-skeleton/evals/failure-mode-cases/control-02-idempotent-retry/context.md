# Retry upsert on transient errors

**Repo:** example-org/example-app-sdk-py (synthetic fixture)

## PR description

Retry `client.upsert` on 5xx and read-timeouts with exponential backoff. Each call sends an `Idempotency-Key` header that is reused across its attempts.

## Intent

Better handling of transient server errors.
