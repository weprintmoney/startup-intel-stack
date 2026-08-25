# sales-ops — Agent Identity and Security Rules

This repo runs the automated outbound pipeline for <YOUR_COMPANY>: find,
qualify, and enroll ICP-fit contacts in a human-approved email sequence.
Every agent in this repo operates under the hard rules below.

## Working in this repo (all Claude sessions)

Multiple Claude sessions routinely share the checkout at `~/sales-ops`.
**Never `git checkout` a branch in the shared checkout** — it yanks the
working tree out from under any concurrent session. Branch via worktree
only:

```bash
git worktree add /tmp/<slug> -b <branch> origin/main
# ... work, commit, push, PR ...
git worktree remove /tmp/<slug>
```

The shared checkout stays on `main`; pull with `--ff-only` only.

## SSOT: where the truth lives

Rubrics, ICP criteria, sequence templates, and competitor lists are
canonical in `<YOUR_ORG>/internal-docs/03-commercial-revenue/`. Agents in
this repo read them at runtime via `INTERNAL_DOCS_PAT` (checkout at
`internal-docs/`, a gitignored path). Never hardcode ICP taxonomy,
rubric criteria, or email copy in this repo.

Lead data — named prospects, enriched records, drafts, verdicts, sends,
suppression list — stays in this repo (which must be private) and is
never mirrored to `internal-docs`.

## Hard rules — never break these

1. **Human approval required before first email.** Approval = a human
   merging the enrollment PR. `sequence-enrollment.yml` drafts queue
   files on a branch and opens a PR; nothing sends until the PR is
   reviewed and merged to main. Closing the PR rejects the batch.
2. **Check suppression before every send.** Call `suppression.check(email)`
   from `lib/suppression.py` before every SMTP send. If suppressed, skip
   silently and log.
3. **EU contacts → LinkedIn only.** Call `eu_router.is_eu(country_code)`
   from `lib/eu_router.py`. EU contacts are never sent SMTP emails —
   flag as `outreach_channel: linkedin_only` in the CRM and post a Slack
   action item.
4. **Never name target prospects in `internal-docs`.** Named lead data
   lives in this repo only. Sequence templates (no names) live in
   `internal-docs/03-commercial-revenue/sequences/`.
5. **Pause on reply.** The moment `reply-monitor.yml` detects a reply,
   set `sequence_status: paused` in the CRM and Slack-notify <PM_NAME>
   + <FOUNDER_NAME>. No further automated sends.
6. **Respect `SEQUENCES_PAUSED`.** Check GitHub repo variable
   `SEQUENCES_PAUSED` before every send batch. If `true`, skip entire
   batch and log. `deliverability-monitor.yml` sets this automatically
   on complaint-rate breach.
7. **Never send from the apex domain.** SMTP goes through
   `mail.<your-send-domain>` only. Apex-domain sends destroy your
   corporate email reputation.
8. **Production cap: 100 emails/day.** Hard-coded in `lib/smtp_send.py`.
   Raise it only after 30 days of clean warmup and deliverability.
9. **Fail-closed at both rubric gates.** If the qualifier-critic wrote
   no verdict for a lead, dedup-review refuses to upsert. If the
   copy-evaluator wrote no verdict for a draft, sequence-enrollment
   refuses to open the approval PR. Missing verdicts halt the pipeline;
   they do not skip the gate.

## The two rubric gates

The pipeline has two LLM judges. Both run headless in CI, both read
their rubric from `internal-docs` at runtime, and both fail closed.

| Gate | Where | What it protects |
|---|---|---|
| **Qualifier-critic** (`agents/qualifier-critic/`) | `dedup-review.yml` between enrichment and CRM upsert | Reputation — filters leads that shouldn't be contacted, before anything gets written to the CRM |
| **Copy-evaluator** (`agents/copy-evaluator/`) | `sequence-enrollment.yml` between drafting and approval-PR | Brand voice + factual grounding — filters drafts that shouldn't be sent, before a human sees them |

Both gates are backed by golden-set regression tests in `evals/`.
`judge-evals.yml` reruns them weekly and on any PR that touches the
prompts or fixtures; a verdict flip fails the build.

## Critic warmup override

`dedup-review.yml` accepts a `warmup_mode` boolean input. When true,
top-N FAIL verdicts (score ≥ `warmup_score_floor`, no hard-block hits)
are promoted to PASS so a real-send warmup can proceed while the
qualifier-critic rubric is being tuned for cold outbound. The rubric
itself is untouched; promoted records carry `warmup_promoted: true` and
`original_decision: "FAIL"` for audit. Copy-evaluator still gates draft
quality downstream. **Turn off once the rubric is calibrated for
pre-first-touch scoring.**

## CRM field schema (for `lib/attio.py`)

Set up by `scripts/attio_schema_setup.py`.

| Field | Type | Description |
|---|---|---|
| `email` | string | Primary contact email |
| `company_name` | string | Company name |
| `contact_title` | string | Job title |
| `icp_segment` | enum | Your ICP segments — defined in `internal-docs/03-commercial-revenue/icp-filter-criteria.yaml`; the setup script reads that list and writes it into the CRM enum options |
| `sequence_status` | enum | `pending` / `enrolled` / `completed` / `paused` / `rejected` — set to `pending` on upsert; smtp-send sets `enrolled` when touch-1 sends |
| `sequence_enrolled_date` | date | When enrolled into CRM sequence |
| `last_touch_date` | date | Last send date |
| `last_touch_number` | int | Which touch (1–N) |
| `reply_received` | bool | Whether a reply was detected |
| `outreach_channel` | enum | `email` / `linkedin_only` |
| `eu_contact` | bool | True if EU/EEA-domiciled |
| `suppressed` | bool | True if on suppression list |
| `pain_point` | text | Segment-specific pain point for sequence personalization |
| `vertical_proof` | text | One-sentence proof point for the contact's ICP segment |
| `touch_2_subject` | text | Pre-computed subject line for touch 2 |
| `touch_2_scenario` | text | Pre-computed body scenario for touch 2 |

## Provenance

CI agents that commit output add trailers:

```
Agent: <agent-name>
Agent-Model: claude-<model-tag>
Triggered-By: <workflow-name>
```

## Secret names (GitHub repo secrets)

See [`.env.example`](.env.example) for the annotated list — what each
secret is for, which workflow reads it, and how to scope it.
