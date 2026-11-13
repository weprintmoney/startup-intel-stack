---
title: "Spec: startup check for legacy EXAMPLE_APP_STORE_URL"
status: draft
---

# Spec: fail fast when a legacy `EXAMPLE_APP_STORE_URL` is set

## 1. Goal

Operators upgrading from v0.32.x still have `EXAMPLE_APP_STORE_URL` in
their environment. The service ignores it silently and starts on the `disk`
default, so an operator who used to "back it with Postgres" sees an empty
queue and assumes its jobs were lost. Detect the stale variable and exit with a
migration message.

## 2. Current behavior (verified against source)

- The `postgres` and `redis` backends were removed in v0.33.0 and
  `EXAMPLE_APP_STORE_URL` was replaced by `EXAMPLE_APP_DATA_DIR` and the
  `EXAMPLE_APP_S3_*` variables (release notes v0.33.0, breaking changes;
  `src/example_app/storage/factory.py:5`).
- `STORE_URL` is not read anywhere: not present in
  `src/example_app/service/config.py` (grep `STORE_URL`: no hits — the
  comment at `src/example_app/service/config.py:6` only records its removal).
- The store selector defaults to `disk` — `src/example_app/service/config.py:7`.
- MySQL was never a supported backend (terminus/invariants NF-01); the
  migration message must not suggest it.

## 3. Graph nodes consulted

- `component/backing-stores` — behavior matrix rows for `postgres` and
  `redis` carry `removed_in: "0.33.0"`.
- `terminus/invariants` — NF-01 (no relational backing store).

## 4. Design

Add a startup check in `config.py`: if `EXAMPLE_APP_STORE_URL` is set,
exit non-zero with a message naming `EXAMPLE_APP_STORE`, `EXAMPLE_APP_DATA_DIR`
and the v0.33.0 migration guide. Rejected alternative: warn and continue —
the failure mode we are fixing is exactly "started fine, wrong data".

## 5. Acceptance criteria

- [ ] `EXAMPLE_APP_STORE_URL=postgres://…` → exit 2 with migration text
- [ ] Unset → no behavior change
- [ ] Message names `disk` and `s3` only

## 6. Open questions

None.

## 7. References

- Release notes v0.32.0 (deprecation) and v0.33.0 (removal).
