# Pipeline Agents

Lead pipeline, in order. Each agent has its own folder with a `CLAUDE.md` defining its contract; workflows in `.github/workflows/` invoke them. All read `company-profile.yaml` for ICP criteria, thresholds, and cadences.

| # | Agent | In → Out | Mode |
|---|-------|----------|------|
| 1 | crawler | ICP criteria → `leads/raw/` via Apollo people search (skipped without `APOLLO_API_KEY`); also searches people at companies waiting in `leads/companies/` | find-leads |
| 1b | apify-ingest | Apify actors (public-page LinkedIn people search + company-employees, Google Maps company discovery, job-posting signals, Meetup events) → `leads/raw/`, `leads/companies/`, `docs/01-market-intelligence/event-candidates.md` (requires `APIFY_API_KEY`; off until `apify_sources.enabled`) | find-leads |
| 2 | event-ingest | event CSV/XLSX → `leads/raw/` | find-leads |
| 3 | dedup | `leads/raw/` → `leads/deduped/` (checks CRM via adapter) | find-leads |
| 4 | pre-filter | hard ICP gates (incl. metro when `icp.locations` is set) + competitor suppression → `leads/pre-filtered/` | find-leads |
| 5 | enrichment | email finding (Prospeo → Apollo → Hunter, whichever keys exist) + signal research → `leads/enriched/` | find-leads |
| 6 | stack-profile **or** org-context-profile | per-company research selected by `icp.profile_agent`: tech stack from public code (`leads/stack-profiles/`) or organisation context — metro presence, People leader, people-side signals, culture language (`leads/org-profiles/`) | find-leads |
| 7 | qualifier-critic | rubric verdict (ICP fit, metro presence when configured, pain evidence, reachability, timing, disqualifiers) → `leads/critic/` | find-leads |
| 8 | sequence-enrollment | drafts personalized touches → **approval PR** | find-and-draft |
| 9 | copy-evaluator | blind rubric on every draft; hard-blocks bad copy | find-and-draft |
| 10 | send + reply-monitor + deliverability | provider send within caps, pause on reply, kill switch on complaints — **or, when `sending.provider: manual`,** `manual-send-packet.yml` turns each approved batch into a copy-paste packet plus one GitHub issue per lead, and `lead-issue-sync.yml` writes the human's checkbox/label actions back into the local CRM | find-and-draft |
| 11 | evergreen-nurture | re-engage completed/no-reply after 21+ days | find-and-draft |
| 12 | feedback-loop | monthly: mine approval-PR edits (and, in manual mode, `sends/outcomes.jsonl`) → propose rubric/template fixes | find-leads |

Mode column uses the `company.mode` names; an agent needs that mode or higher to run.

Confidentiality: rule 6 in `CLAUDE.md` bans named prospects in issues. Instances running `sending.provider: manual` keep contact names in issues labelled `lead` — those issues are the CRM. Everywhere else the rule stands.

All agents above are live in the template's L2 scaffold; see `README.md` → Modes for what runs at each mode.
