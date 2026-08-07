# leads/ — Pipeline Data

Working data for the sales pipeline agents. Folder flow:

`raw/` (crawler, event-ingest) → `deduped/` → `pre-filtered/` (+ rejects) → `enriched/` → `stack-profiles/` → `critic/` (qualification verdicts) → sequence enrollment.

`crm-local/` — JSONL contact store used when `crm.provider: none` in company-profile.yaml.

**Confidentiality:** everything under `leads/` is named-prospect data. It never leaves this instance repo — never copy it into docs, issues, other repos, or the upstream template. This is why instance repos must stay private.
