---
title: "Invariants (Terminus 1b) — FIXTURE"
graph_id: terminus/invariants
graph_type: architectural-decision
confidence: observed
---

# Invariants (Terminus 1b) — condensed fixture

Synthetic excerpt for the claim-verify golden set. Behavioral invariants
(INV-xx) say what must always be true; design boundaries (BND-xx) and
non-features (NF-xx) are the negative space — what example-app deliberately
is not, so spec and grooming agents stop inventing features.

## Behavioral invariants

### INV-01: Every job is written to the backing store before its enqueue call is acknowledged.

## Design boundaries

### BND-01: No unauthenticated mode. Authentication is not a runtime toggle.

There is no build-time flag, runtime flag, per-queue setting, or per-request
option that disables authentication. `--dev` mode (ADR-0031) generates a
local root token and still authenticates. Any spec that compares
"example-app with and without authentication" is invalid.

### BND-02: Single queue type. example-app ships one durable queue (ADR-0007).

There is no fifo / priority / delayed queue selection and no `queue_config`
object since v0.33.0.

## Non-features

### NF-01: No relational or key-value database backing store.

The storage surface is `memory`, `disk` (embedded LMDB) and `s3`
(S3-compatible object stores). The `postgres` and `redis` backends were
removed in v0.33.0; `embedded` was renamed to `disk`. MySQL was never
supported. Source: `versions/changelog.mdx` (v0.33.0 breaking changes),
`backing-stores/behavior-matrix.yaml`.

### NF-02: No workflow/DAG engine or DAG parameters (`run_after`, `fan_in`).
