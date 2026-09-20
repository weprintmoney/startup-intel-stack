# schemas/

One JSON Schema (Draft 2020-12) per data-file shape, validated by
`lib/validate_data.py`.

| Directory / file | Schema | Notes |
|---|---|---|
| `leads/raw/*.json` (array) | `lead-raw` | Written by crawler, apify-ingest and event-ingest. Optional metro fields (`contact_location`, `company_hq_location`, `metro_match`, `metro_evidence`) and source fields (`signal`, `evidence_url`, `source_actor`, `source_run_id`, `source_id`) flow through every lead stage |
| `leads/companies/*.json` (array) | `company-lead` | apify-ingest's company-only records (Maps, job postings); `people_searched_date` marks them consumed |
| `leads/deduped/*.json` (array) | `lead-deduped` | lead-raw + `prior_contact` |
| `leads/pre-filtered/*.json` except `*-rejects.json` (array) | `lead-pre-filtered` | Passed pre-filter's structural gate |
| `leads/pre-filtered/*-rejects.json` (array) | `lead-reject` | Failed the gate; diverges from lead-pre-filtered (no `eu_flagged`/`mql_score` requirement, adds `reject_reason`) |
| `leads/enriched/*.json` (array) | `lead-enriched` | lead-pre-filtered + email-finder result + opportunistic signal fields |
| `leads/critic/*.json` (array) | `critic-verdict` | Qualifier-critic's rubric output |
| `leads/org-profiles/*.json` (array) | `org-context-profile` | Org-context-profile agent's per-lead organisation inference (fixed dimension set; `{value, confidence, evidence}` per field) |
| `sends/queue/*.json` (one object per file) | `send-touch` | Email touches, sent by smtp-send |
| `sends/linkedin/*.json` (one object per file) | `send-touch` | LinkedIn touches, sent manually |
| `sends/rejected/*.json` (one object per file) | `send-touch` | Moved here unmodified by the copy-evaluator gate |
| `sends/format-test-queue/*.json` (one object per file) | `send-touch-format-test` | Extends send-touch with 3 required keys: `original_to`, `reply_to`, `campaign` |
| `sends/verdicts/*.json` (array) | `copy-verdict` | Copy-evaluator's rubric output |
| `suppression/list.jsonl` (JSON Lines) | `suppression-line` | `reason` enum must stay in sync with `lib/suppression.py`'s `VALID_REASONS` |
| `sends/daily-count.json` (one object) | `daily-count` | Overwritten in place, not a per-day log |
| `sends/outcomes.jsonl` (JSON Lines) | `outcome-line` | Manual-send outcomes: `touch_sent` / `replied` / `booked` / `no_response` / `do_not_contact` / `note`, written by `lead-issue-sync.yml` from `lead` issues or appended by hand |

Not schema'd: `sends/manual/*.md` (rendered packets — prose, regenerated from the queue files), and any additional per-instance data directories you add that
don't yet have a producer, or that are working notes rather than a
pipeline-consumed shape. Add a schema here before wiring a new stage's
output into `lib/validate_data.py`.

Every synthetic example in this directory and in the agent prompts that
reference these schemas should use made-up companies/contacts — never a
real prospect name, per the no-target-prospect-naming convention (see
CLAUDE.md).
