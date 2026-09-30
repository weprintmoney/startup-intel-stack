# Notes (not shown to the reviewer)

**Mirrors:** `retries-without-idempotency` (DDIA §8 exactly-once) — clean counterpart, kind=control.

## Why it is clean

Same retry loop, same `RETRY_ON` set, same backoff as the buggy fixture. The difference: the client mints one `uuid4` idempotency key per logical `upsert` call and sends it as an `Idempotency-Key` header on every attempt, and the diff states the server dedupes on that key for 24h. A retry after a lost response therefore replays into a server-side no-op instead of duplicating the batch. A reviewer should approve; asking for an idempotency key here is a false positive.

Calls `response.raise_for_status()` before returning — httpx does not raise on a 4xx/5xx response by default, so without it the `except (HTTPStatusError, ReadTimeout)` clause never fires on a real server error and the retry loop is dead code (a real defect founder-voice-pr-reviewer caught in an earlier draft of this fixture; fixed 2026-09-12).
