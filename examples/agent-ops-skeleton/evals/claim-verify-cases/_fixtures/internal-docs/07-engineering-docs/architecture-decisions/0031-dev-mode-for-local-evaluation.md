---
title: "ADR-0031: Dev mode for local evaluation — FIXTURE"
graph_id: adr-0031
status: accepted
---

# ADR-0031 (fixture)

**Decision.** `--dev` generates a local root token so evaluators can start
without an identity provider. Requests are **still authenticated** — dev
mode changes where the token comes from, not the authentication path.

**Rejected.** Making authentication optional entirely (no token on
single-node deployments): the security posture becomes ambiguous.
