---
title: "Spec: validate and document EXAMPLE_APP_S3_PREFIX"
status: draft
---

# Spec: validate and document `EXAMPLE_APP_S3_PREFIX`

## 1. Goal

Operators using the `s3` backing store can set an object-key prefix but the
service never validates it. This spec adds validation (no leading `/`, no
`..` segments) and a docs page.

## 2. Current behavior (verified against source)

- The service reads the prefix from `EXAMPLE_APP_S3_PREFIX`, default `""` —
  `src/example_app/service/config.py:10`.
- The backing-store surface is `memory`, `disk` and `s3`
  (`src/example_app/storage/factory.py:14`); `disk` is the default
  (`src/example_app/service/config.py:7`). Anything else raises `ValueError`
  (`src/example_app/storage/factory.py:26`).
- The S3 store receives the prefix through `make_store`
  (`src/example_app/storage/factory.py:25`).
- No validation of the prefix exists today: not present in
  `src/example_app/service/config.py` or `src/example_app/storage/factory.py`
  (grep `prefix`).

## 3. Graph nodes consulted

- `component/backing-stores` — canonical rows for `s3` (supported since
  v0.15.0, per the behavior matrix).
- `claim/tiered-storage-memory-disk-s3` — positioning depends on the S3
  tier working out of the box; a bad prefix silently writing to the bucket
  root undermines it.
- `terminus/invariants` — INV-01 is unaffected: the prefix is a key
  layout choice, not an encryption boundary.
- `adr-0001` — no interaction; single DiskIVF index type is orthogonal.

## 4. Design

Validate in `config.py` at import time; raise a config error listing the
offending prefix. Rejected alternative: validate lazily in `S3Store`
(surfaces on first write, which is too late for an operator).

## 5. Acceptance criteria

- [ ] `EXAMPLE_APP_S3_PREFIX=/foo` fails fast with a clear error
- [ ] `EXAMPLE_APP_S3_PREFIX=team-a/prod` accepted
- [ ] Docs page under the v0.17.x service guides

## 6. Open questions

None — (a) policy, (b) runtime facts, (c) roadmap context: none apply.

## 7. References

- Release notes v0.17.0 — storage refactor introduced `EXAMPLE_APP_S3_*`.
