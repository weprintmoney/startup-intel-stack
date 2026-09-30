---
title: "Spec: connection-pool tuning for the Postgres backing store"
status: draft
---

# Spec: connection-pool tuning for the Postgres backing store

## 1. Goal

Large ingests saturate the Postgres connection pool. Expose pool size and
timeout knobs so operators can tune for bulk upsert.

## 2. Current behavior (verified against source)

- example-app supports Postgres storage; the service selects it through
  `EXAMPLE_APP_CONNECTION_STRING` (`src/example_app/service/config.py:7`).
- The pool is created with a fixed size of 16 in
  `src/example_app/storage/postgres_pool.py:12`.
- The disk store is the default for embedded use
  (`src/example_app/service/config.py:7`).

## 3. Graph nodes consulted

- `component/backing-stores` — Postgres row.
- `adr-0041` — the decision to keep Postgres as the primary service store.
- `terminus/performance-budgets` — bulk-upsert throughput floor.

## 4. Design

Add `EXAMPLE_APP_PG_POOL_SIZE` (default 16) and `EXAMPLE_APP_PG_POOL_TIMEOUT_MS`
(default 5000). Rejected alternative: auto-size from CPU count — hides the
knob operators asked for.

## 5. Acceptance criteria

- [ ] Pool size honored at startup
- [ ] Timeout surfaces as a 503 with error code `STORE_POOL_TIMEOUT`

## 6. Open questions

None.

## 7. References

- Release notes v0.17.0.
