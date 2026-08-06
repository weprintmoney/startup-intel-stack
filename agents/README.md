# Pipeline Agents

Lead pipeline, in order. Each agent has its own folder with a `CLAUDE.md` defining its contract; workflows in `.github/workflows/` invoke them. All read `company-profile.yaml` for ICP criteria, thresholds, and cadences.

| # | Agent | In → Out | Tier |
|---|-------|----------|------|
| 1 | crawler | ICP criteria → `leads/raw/` (requires Apollo key; skipped without) | seed |
| 2 | event-ingest | event CSV/XLSX → `leads/raw/` | seed |
| 3 | dedup | `leads/raw/` → `leads/deduped/` (checks CRM via adapter) | seed |
| 4 | pre-filter | hard ICP gates + competitor suppression → `leads/pre-filtered/` | seed |
| 5 | enrichment | email finding + signal research (funding, hiring, pain) → `leads/enriched/` | seed |
| 6 | stack-profile | infer tech stack from public sources → `leads/stack-profiles/` | seed |
| 7 | qualifier-critic | rubric verdict (ICP fit, pain evidence, reachability, timing, disqualifiers) → `leads/critic/` | seed |
| 8 | sequence-enrollment | drafts personalized touches → **approval PR** | series-a |
| 9 | copy-evaluator | blind rubric on every draft; hard-blocks bad copy | series-a |
| 10 | send + reply-monitor + deliverability | Resend send within caps; pause on reply; kill switch on complaints | series-a |
| 11 | evergreen-nurture | re-engage completed/no-reply after 21+ days | series-a |
| 12 | feedback-loop | monthly: mine approval-PR edits → propose rubric/template fixes | seed |

Porting status per agent: see `EXTRACTION.md`. None are live in the template yet.
