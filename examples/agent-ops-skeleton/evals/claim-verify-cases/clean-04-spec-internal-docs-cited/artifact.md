---
title: "Spec: batch enqueue acknowledges only after the durable write"
status: draft
---

# Spec: batch enqueue acknowledges only after the durable write

## 1. Goal

Operators want a batch endpoint that enqueues many jobs in one request
(e.g. a nightly fan-out of report jobs). The batch path must not
acknowledge jobs that are still sitting in an in-process buffer.

## 2. Current behavior (verified against source)

- Every job is written to the backing store before its enqueue call is
  acknowledged — `07-engineering-docs/terminus/invariants.md:17`
  (INV-01). A batch path that acknowledged from a write-behind buffer
  would violate this invariant.

## 3. Graph nodes consulted

- `terminus/invariants` — INV-01 governs this design; BND-01 (no
  unauthenticated mode) rules out an "internal, token-less batch
  endpoint" opt-in.

## 4. Design

Acknowledge the batch only once every job in it has been written — the
same point INV-01 requires for a single enqueue
(`07-engineering-docs/terminus/invariants.md:17`); no new buffer, no new
storage surface. Rejected alternative: a write-behind buffer that
acknowledges first for throughput — INV-01 forbids it outright.

## 5. Acceptance criteria

- [ ] A batch of N jobs returns N job ids, all present in the backing
      store
- [ ] A crash between request and acknowledgement loses no acknowledged
      job
- [ ] A batch over the size limit is rejected at request time

## 6. Open questions

None.

## 7. References

- `terminus/invariants` INV-01, BND-01.
