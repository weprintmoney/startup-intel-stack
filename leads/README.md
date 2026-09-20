# leads/ — Pipeline Data

Working data for the sales pipeline agents. Folder flow:

`raw/` (crawler, apify-ingest, event-ingest) → `deduped/` → `pre-filtered/` (+ rejects) → `enriched/` → `org-profiles/` (the profile stage named by `icp.profile_agent`) → `critic/` (qualification verdicts) → sequence enrollment.

`companies/` — company-only leads (no contact yet) from apify-ingest's discovery and signal sources; apify-ingest's LinkedIn company-employees source (or the crawler, when an Apollo key exists) later finds people there and stamps `people_searched_date`.

`crm-local/` — JSONL contact store used when `crm.provider: none` in company-profile.yaml.

**Confidentiality:** everything under `leads/` is named-prospect data. It never leaves this instance repo — never copy it into docs, issues, other repos, or the upstream template. This is why instance repos must stay private.
