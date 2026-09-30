---
title: "Spec: metadata filter allowlist evaluates inside the encryption boundary"
status: draft
---

# Spec: metadata filter allowlist evaluates inside the encryption boundary

## 1. Goal

Operators want to filter vector queries by customer-provided metadata
fields (e.g. `tenant_id`, `doc_type`). The filter evaluator must not create
a plaintext side-channel index over those fields.

## 2. Current behavior (verified against source)

- Every vector and every customer-provided metadata field is encrypted
  before it reaches any backing store — `07-engineering-docs/terminus/invariants.md:17`
  (INV-01). A metadata filter index built outside the encryption boundary
  would violate this invariant.

## 3. Graph nodes consulted

- `terminus/invariants` — INV-01 governs this design; PSI-01 (no plaintext
  mode) rules out an "unencrypted filter index" opt-in.

## 4. Design

Evaluate filters at the point where a vector is decrypted for scoring —
inside the boundary INV-01 requires for the vector itself
(`07-engineering-docs/terminus/invariants.md:17`); no new index, no new
storage surface. Rejected alternative: a separate plaintext metadata
index for filter speed — INV-01 forbids it outright.

## 5. Acceptance criteria

- [ ] Filtering by an allowlisted metadata field returns correct results
- [ ] No plaintext copy of any metadata field is ever written to a backing
      store
- [ ] Filtering by a non-allowlisted field is rejected at request time

## 6. Open questions

None.

## 7. References

- `terminus/invariants` INV-01, PSI-01.
