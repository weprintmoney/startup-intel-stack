# schemas/

One JSON Schema (Draft 2020-12) per data-file shape, validated by
`lib/validate_data.py`.

| Directory / file | Schema | Notes |
|---|---|---|
| `leads/raw/*.json` (array) | `lead-raw` | Written by crawler and event-ingest |
| `leads/deduped/*.json` (array) | `lead-deduped` | lead-raw + `prior_contact` |
| `leads/pre-filtered/*.json` except `*-rejects.json` (array) | `lead-pre-filtered` | Passed pre-filter's structural gate |
| `leads/pre-filtered/*-rejects.json` (array) | `lead-reject` | Failed the gate; diverges from lead-pre-filtered (no `eu_flagged`/`mql_score` requirement, adds `reject_reason`) |
| `leads/enriched/*.json` (array) | `lead-enriched` | lead-pre-filtered + email-finder result + opportunistic signal fields |
| `leads/critic/*.json` (array) | `critic-verdict` | Qualifier-critic's rubric output |
| `leads/stack-profiles/*.json` (array) | `stack-profile` | Stack-profile agent's per-lead tech-stack inference |
| `sends/queue/*.json` (one object per file) | `send-touch` | Email touches, sent by smtp-send |
| `sends/linkedin/*.json` (one object per file) | `send-touch` | LinkedIn touches, sent manually |
| `sends/rejected/*.json` (one object per file) | `send-touch` | Moved here unmodified by the copy-evaluator gate |
| `sends/format-test-queue/*.json` (one object per file) | `send-touch-format-test` | Extends send-touch with 3 required keys: `original_to`, `reply_to`, `campaign` |
| `sends/verdicts/*.json` (array) | `copy-verdict` | Copy-evaluator's rubric output |
| `suppression/list.jsonl` (JSON Lines) | `suppression-line` | `reason` enum must stay in sync with `lib/suppression.py`'s `VALID_REASONS` |
| `sends/daily-count.json` (one object) | `daily-count` | Overwritten in place, not a per-day log |

Not schema'd: any additional per-instance data directories you add that
don't yet have a producer, or that are working notes rather than a
pipeline-consumed shape. Add a schema here before wiring a new stage's
output into `lib/validate_data.py`.

Every synthetic example in this directory and in the agent prompts that
reference these schemas should use made-up companies/contacts — never a
real prospect name, per the no-target-prospect-naming convention (see
CLAUDE.md).
