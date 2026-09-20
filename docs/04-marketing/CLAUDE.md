# 04 — Marketing

Content production and monitoring. Contents:

- `content-ops/` — runbook + reference docs: `claims-vetted.md` (the ONLY claims agents may use — starts empty, founder adds vetted claims), taxonomy, frontmatter schemas, drafts/
- `launch-playbook.md` — generic launch checklist (roles, gates, comms templates); instantiate per launch with a dated plan file
- `site-messaging-map.md` — persona × page-section × frame checklist; the operational layer under the messaging house
- `aeo/queries.yaml` — the tracked answer-engine queries (ids, segments, priorities), `brand_terms`, `competitor_terms`, and the alert threshold; `aeo-monitoring.yml` reads this first. Start from `aeo/queries.example.yaml`.
- `aeo/YYYY-MM-DD-aeo-results.md` — dated monitoring output (queries, hit/miss per engine, coverage, delta); `aeo-gap` issues are filed for critical/high misses. The topic-cluster health map also lands here as a dated file.
- `archive/` — stale/superseded docs; guarded by its own CLAUDE.md, never loaded for active work

Mode: content ops and AEO monitoring run in every mode, including `docs-only` — they never touch contact data. Content generation still halts while `content-ops/claims-vetted.md` carries its SETUP NOTE.
