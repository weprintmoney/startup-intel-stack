# sales-ops skeleton

A worked example of **Level 2 — the first production loop** from
[*Context, Loops, Graphs*](../../docs/00-foundations/context-loops-graphs.md).

Cold prospects in → rubric-gated, human-approved outreach out. The pipeline
is GitHub Actions all the way down. LLM judges gate the two moments that
actually matter (should we contact this lead? does this draft respect the
brand?); everything else is deterministic.

This is a template. All company-specific values are `<YOUR_ORG>`,
`<YOUR_COMPANY>`, `<FOUNDER_NAME>`, `<PM_NAME>`, `<primary-competitor>`,
`<paying-customer>`, `<segment-a/b/c>`, or `${{ secrets.SLACK_*_ID }}`
placeholders. See "Making this real" below.

---

## What's in here

The file surface is the same as a real Level-2 outbound loop. What runs
against what changes with your product and ICP; the shape doesn't.

| Path | What it is |
|---|---|
| `agents/<name>/CLAUDE.md` | One prompt per pipeline node — invoked as `claude -p "$(cat agents/<name>/CLAUDE.md)"` |
| `.github/workflows/` | Every stage as a workflow: `weekly-crawl`, `event-ingest`, `dedup`, `pre-filter`, `enrichment`, `stack-profile`, `dedup-review` (qualifier-critic gate), `sequence-enrollment` (copy-evaluator gate + approval PR), `smtp-send`, `reply-monitor`, `deliverability-monitor`, `evergreen-nurture`, `warmup`, `judge-evals`, `pipeline-heartbeat`, `feedback-loop`, `run-sales-pipeline` (one-button orchestrator) |
| `lib/` | Shared Python: `attio.py` (CRM adapter), `suppression.py` (blocklist check), `eu_router.py` (EU/EEA gate), `smtp_send.py` (Resend send + daily-cap enforcement), `imap_poll.py` (reply monitoring), `exa_search.py` (neural search wrapper for signal research) |
| `leads/` | Pipeline data — one folder per lifecycle stage. Everything under `leads/**` is `.gitignored` in this skeleton so a downstream user can't accidentally commit real lead data. The `.gitkeep` files preserve the directory shape |
| `sends/` | Live send state — `queue/`, `log/`, `verdicts/`, `rejected/`, `daily-count.json`. Also gitignored except for `daily-count.json`'s initial stub |
| `suppression/` | `list.jsonl` — the send blocklist (empty in this skeleton). Schema in `suppression/README.md` |
| `warmup/` | Domain-warmup send logs |
| `feedback/reports/` | Where the monthly feedback-loop agent writes its correction-cluster report |
| `evals/` | Golden-set regression harness for the two judges — see `evals/README.md`. Ships one hand-written toy fixture per judge; your real build wants 10-20 |
| `inbox-agent/` | Standalone Fly.io service — sales-ops calls it to check "has the founder already contacted this address?" against Gmail before enrolling a lead |
| `slack-webhook/` | Cloudflare Worker for one-click unsubscribe from the send footer |
| `scripts/attio_schema_setup.py` | Idempotently provisions the custom People attributes the CRM adapter expects |

## How this maps to the paper

Read [`../../docs/00-foundations/context-loops-graphs.md`](../../docs/00-foundations/context-loops-graphs.md) first if you haven't.
This skeleton lays out one workflow per paper phase for L2 outbound.

| Paper phase | This skeleton |
|---|---|
| L2-0 Plumbing + safety floor | `.gitignore`, `suppression/`, `SEQUENCES_PAUSED` variable, `lib/eu_router.py`, `.github/workflows/deliverability-monitor.yml`, `.github/workflows/pipeline-heartbeat.yml` |
| L2-1 First loop end-to-end | `weekly-crawl.yml` / `event-ingest.yml` → `dedup.yml` → `pre-filter.yml` → `enrichment.yml` → `stack-profile.yml` → `dedup-review.yml` (qualifier-critic gate) → `sequence-enrollment.yml` (copy-evaluator gate + approval PR) → `smtp-send.yml` + `reply-monitor.yml`. The **rubric gates** (qualifier-critic 23-criterion + copy-evaluator 24-criterion) live in `<YOUR_ORG>/internal-docs` — read at runtime, edited there, not here |
| L2-2 Regression harness + feedback loop | `evals/` (golden-set fixtures + `run_eval.py`), `.github/workflows/judge-evals.yml` (weekly + on-PR verdict-flip check), `.github/workflows/feedback-loop.yml` (monthly correction-cluster report + rubric-proposal PR to internal-docs) |

## The outbound loop, in flow

```
weekly Apollo crawl OR event CSV ingest
  → dedup.yml          against your CRM (prior contacts filtered)
  → pre-filter.yml     ICP gate vs internal-docs/icp-filter-criteria.yaml
                       (cheap; no API spend on rejects)
  → enrichment.yml     Apollo/Hunter emails + signal research (funding,
                       hiring, launches, pain evidence — feeds the
                       critic's evidence categories). Uses EXA neural
                       search
  → stack-profile.yml  Architecture inference per company; per-field
                       confidence-scored. Sequence-enrollment only asserts
                       stack claims at confidence ≥60
  → dedup-review.yml   QUALIFIER-CRITIC GATE — 23-criterion rubric,
                       pass threshold ≥70. FAIL = not upserted.
                       ESCALATE = listed in run summary. Fail-closed:
                       no verdict = no upsert
  → sequence-enrollment.yml
                       Drafts personalized touches; COPY-EVALUATOR GATE
                       (24-criterion, pass ≥80). FAIL drafts → sends/rejected/.
                       Opens APPROVAL PR with verdict table. Nothing sends
                       until the PR is merged
  → smtp-send.yml      Hourly M-F: SEQUENCES_PAUSED check → suppression
                       check → 100/day cap → Resend send. Hard bounce →
                       auto-suppress. Soft bounce → Slack
  → reply-monitor.yml  Hourly M-F IMAP poll; reply pauses sequence,
                       unsubscribe auto-suppresses
```

Failure contract at every stage: **fail closed**. Missing verdicts stop
the pipeline rather than letting ungated output through. The
`SEQUENCES_PAUSED=true` repo variable is the global kill switch;
`deliverability-monitor.yml` sets it automatically when the complaint
rate crosses 0.1%.

## Making this real

This skeleton runs no-op — every workflow gates on secrets that don't
exist yet. To land it in your org:

1. **Replace the placeholders.** Search the tree for `<YOUR_ORG>`,
   `<YOUR_COMPANY>`, `<FOUNDER_NAME>`, `<PM_NAME>`, `<SALES_LEAD_NAME>`,
   `<PM_EMAIL>`, `<FOUNDER_EMAIL>`, `<pm-github-handle>`,
   `<founder-github-handle>`, `<primary-competitor>`, `<paying-customer>`,
   `<segment-a>` / `<segment-b>` / `<segment-c>`, and `<YOUR_PRODUCT_CATEGORY>`.
   Substitute your real values.
2. **Provision the bot account.** Create a `sales-ops-bot` GitHub user
   (or org bot); all workflows commit as this identity via
   `git config user.name "sales-ops-bot"` / `bot@example.com`.
3. **Fill `.env.example` and set the secrets.** The workflows read secrets
   by name from GitHub repo secrets; the file documents what each one is
   for and which workflow reads it.
4. **Rewrite the ICP-filter YAML in your internal-docs SSOT.** All
   rubrics, ICP criteria, sequence templates, and competitor lists live
   in `<YOUR_ORG>/internal-docs/03-commercial-revenue/` and are read at
   runtime via `INTERNAL_DOCS_PAT`. Never hardcode ICP taxonomy or copy
   in this repo.
5. **Fill the segment-personalization dictionaries in
   `.github/workflows/dedup-review.yml`.** The `PAIN_POINTS`,
   `VERTICAL_PROOFS`, `TOUCH_2_SUBJECTS`, and `TOUCH_2_SCENARIOS` maps
   are the deterministic-personalization tier: segment-key → segment-copy.
   The LLM drafting agent handles per-lead personalization on top.
6. **Rewrite `agents/stack-profile/CLAUDE.md` field schema** to match
   your product category. The stack-profile field set
   (`category_incumbent`, `cloud`, `rag_maturity`...) is illustrative —
   4-8 categorical dimensions the prospect's own engineers would
   recognize as their architecture is the pattern to keep.
7. **Build your golden set.** Replace `evals/qualifier-critic/` and
   `evals/copy-evaluator/` toy fixtures with 10-20 historical leads and
   drafts. Historical judge disagreements are the highest-value fixtures.
   The one-fixture skeleton exists to show the harness shape; it can't
   catch drift.
8. **Provision the CRM schema.** Run `python scripts/attio_schema_setup.py
   --dry-run` to see what's missing, then run without `--dry-run` to
   create the custom People attributes. Replace the placeholder
   `icp_segment` enum options first.
9. **DNS + warmup before real outbound.** Set up
   `mail.<your-send-domain>` MX/SPF/DKIM/DMARC, then run
   `warmup.yml` — 28-day phased ramp (20 → 40 → 50/day). Only enable
   `smtp-send.yml`'s hourly cron after `WARMUP_COMPLETE=true`.

## Layout

```
agents/            one CLAUDE.md prompt per pipeline node
                   (12 agents: crawler, event-ingest, dedup, pre-filter,
                    enrichment, stack-profile, qualifier-critic,
                    copy-evaluator, sequence-enrollment, review-queue,
                    evergreen-nurture, feedback-loop)
lib/               shared Python: attio.py, suppression.py, eu_router.py,
                   smtp_send.py, imap_poll.py, exa_search.py
leads/             pipeline data (gitignored; .gitkeeps preserve shape)
sends/             live send state (queue/log/verdicts/rejected +
                   daily-count.json)
suppression/       list.jsonl (blocklist) + README with the schema
warmup/            warmup send logs
feedback/reports/  monthly feedback-loop reports
evals/             judge-evals golden-set harness (one toy fixture ships)
inbox-agent/       standalone Fly.io service for prior-contact lookup
slack-webhook/     Cloudflare Worker for one-click unsubscribe
scripts/           attio_schema_setup.py — idempotent CRM attribute provisioning
.github/
  workflows/       one workflow per pipeline node + orchestrator +
                   judge-evals + pipeline-heartbeat + feedback-loop
  CODEOWNERS       PM owns everything; eng backstops lib/ and agents/
```

## Reading order

1. [`../../docs/00-foundations/context-loops-graphs.md`](../../docs/00-foundations/context-loops-graphs.md) — the paper.
2. [`../../docs/00-foundations/the-coding-harness.md`](../../docs/00-foundations/the-coding-harness.md) — the L3 companion that this L2 loop is a prerequisite for.
3. [`CLAUDE.md`](CLAUDE.md) — hard rules the pipeline enforces.
4. [`.env.example`](.env.example) — the secrets you need to provision.
5. Then walk the workflows in `.github/workflows/` alongside the paper's L2-0 → L2-2 sections.
6. Sibling example: [`../agent-ops-skeleton/`](../agent-ops-skeleton/) — the Level 3 coding harness that builds on top of L2.
