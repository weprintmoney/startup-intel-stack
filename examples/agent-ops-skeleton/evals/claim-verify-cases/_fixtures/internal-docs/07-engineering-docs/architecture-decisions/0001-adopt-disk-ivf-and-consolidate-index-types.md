---
title: "ADR-0001: Adopt Disk IVF and Consolidate to a Single Index Type — FIXTURE"
graph_id: adr-0001
status: accepted
---

# ADR-0001 (fixture)

**Decision.** example-app ships one index type, DiskIVF. The polymorphic
`index_config` object and the IVFFlat / IVFPQ / IVFSQ distinction are
removed. `n_lists` is chosen automatically by the core engine.

**Rejected.** Keeping three index types behind a config object — every
downstream test matrix triples and customers picked wrong.
