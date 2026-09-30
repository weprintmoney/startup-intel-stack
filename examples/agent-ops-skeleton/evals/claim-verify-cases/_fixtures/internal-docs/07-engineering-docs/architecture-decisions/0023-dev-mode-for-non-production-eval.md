---
title: "ADR-0023: Dev mode for non-production evaluation — FIXTURE"
graph_id: adr-0023
status: accepted
---

# ADR-0023 (fixture)

**Decision.** `--dev` generates a local index key so evaluators can start
without a KMS. Data is **still encrypted** — dev mode changes key custody,
not the encryption path.

**Rejected.** Making KMS optional entirely (no encryption at rest in
single-tenant deployments): the security posture becomes ambiguous.
