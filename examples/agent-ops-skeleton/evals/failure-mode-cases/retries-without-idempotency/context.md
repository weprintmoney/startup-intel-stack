# Retry upsert on transient errors

**Repo:** example-org/example-app-sdk-py (synthetic fixture)

## PR description

Retry `client.upsert` on 5xx and read-timeouts with exponential backoff. Improves reliability on flaky network conditions.

## Intent

Better handling of transient server errors.
