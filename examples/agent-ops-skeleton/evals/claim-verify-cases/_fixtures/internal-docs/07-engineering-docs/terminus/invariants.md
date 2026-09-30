---
title: "Invariants (Terminus 1b) — FIXTURE"
graph_id: terminus/invariants
graph_type: architectural-decision
confidence: observed
---

# Invariants (Terminus 1b) — condensed fixture

Synthetic excerpt for the claim-verify golden set. Behavioral invariants
(INV-xx) say what must always be true; product-shape invariants (PSI-xx) and
verified absences (VA-xx) are the negative space — what example-app deliberately
is not, so spec and grooming agents stop inventing features.

## Behavioral invariants

### INV-01: Every vector and every customer-provided metadata field is encrypted before it reaches any backing store.

## Product-shape invariants

### PSI-01: No plaintext mode. Encryption is not a runtime toggle.

There is no build-time flag, runtime flag, per-index setting, or per-request
option that disables encryption. `--dev` mode (ADR-0023) generates a local
key and still encrypts. Any spec that compares "example-app with and without
encryption" is invalid.

### PSI-02: Single index type. example-app ships one DiskIVF index (ADR-0001).

There is no IVFFlat / IVFPQ / IVFSQ selection and no `index_config` object
since v0.17.0.

## Verified absences

### VA-01: No relational or key-value database backing store.

The storage surface is `memory`, `disk` (embedded RocksDB) and `s3`
(S3-compatible object stores). The `postgres` and `redis` backends were
removed in v0.17.0; `standalone` was renamed to `disk`. MySQL was never
supported. Source: `versions/changelog.mdx` (v0.17.0 breaking changes),
`backing-stores/behavior-matrix.yaml`.

### VA-02: No HNSW index or HNSW parameters (`ef_search`, `ef_construction`).
