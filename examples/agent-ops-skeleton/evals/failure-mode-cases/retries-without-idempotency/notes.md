# Notes (not shown to the reviewer)

**Pattern:** `retries-without-idempotency` (DDIA §8 exactly-once)

## Reviewer note

DDIA §8 exactly-once: retrying a write without an idempotency key duplicates the side effect when the server DID commit but the response was lost — the client sees a 502, retries, and now the tenant has two copies of every vector in the batch. Fixes: generate an idempotency key per request (uuid on the client), have the server dedupe on it for a bounded window (24h typical), and document the retry semantic. The retry helper as written is worse than no retry for the "network lost the response" case.
