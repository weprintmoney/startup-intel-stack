---
title: "ADR-0007: Consolidate to a Single Durable Queue Type — FIXTURE"
graph_id: adr-0007
status: accepted
---

# ADR-0007 (fixture)

**Decision.** example-app ships one queue type, the durable queue. The
polymorphic `queue_config` object and the fifo / priority / delayed
distinction are removed. The partition count is chosen automatically by
the core engine.

**Rejected.** Keeping three queue types behind a config object — every
downstream test matrix triples and customers picked wrong.
