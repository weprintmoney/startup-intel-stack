# Examples

Two genericized skeletons of what the field-notes papers under
[`../docs/00-foundations/`](../docs/00-foundations/) describe. Both are
adapted from live implementations, with every company-specific value
templated as `<YOUR_ORG>`, `<YOUR_COMPANY>`, `<FOUNDER_NAME>`,
`<PM_NAME>`, `<primary-competitor>`, `<paying-customer>`,
`<segment-a/b/c>`, or `${{ secrets.SLACK_*_ID }}`.

**These skeletons are for reading, not for running from here.** The
runnable Level 1 + Level 2 lives in the parent template's root
(`../docs/`, `../agents/`, `../lib/`, `../.github/workflows/`). The
skeletons exist so you can crack open concrete workflow YAML, agent
prompts, schemas, and shared libraries alongside the papers — then have
your own Claude adapt them against your stack.

## The two skeletons

| Path | Level | What it shows |
|---|---|---|
| [`sales-ops-skeleton/`](sales-ops-skeleton/) | L2 · Outbound loop | Mature version of the Level 2 rubric-gated outbound pipeline: 23 workflows, 12 agent prompts, 6 shared Python libs, kill switch, EU router, deliverability monitor, monthly feedback-loop, judge-evals regression harness. |
| [`agent-ops-skeleton/`](agent-ops-skeleton/) | L3 · Coding harness | Full Phase 0-6 build: ticket intake, parallel spec drafting, claim-verify gate, plan + implement, two fresh-context reviewers, code-judge with a bounded revise loop, a claim state machine and per-ticket status card, autonomy ledger, dream loop, release intelligence, an enforcing cost ceiling, and Dependabot triage. |

## How these relate to the template's own live code

The parent template's own `agents/` + `.github/workflows/` is a
Level 2 **live scaffold** you can fork and run. `sales-ops-skeleton/`
is the same level but a **mature reference** — more workflows, more
safeguards, more agent surface — for you to study before deciding what
to pull into your instance.

Level 3 is not shipped as a live scaffold in this template. When you're
ready to build it, use `agent-ops-skeleton/` as your starting shape.

## Reading order for a conference-talk audience

1. Read the framework paper: [`../docs/00-foundations/context-loops-graphs.md`](../docs/00-foundations/context-loops-graphs.md)
2. Read the implementation companion: [`../docs/00-foundations/the-coding-harness.md`](../docs/00-foundations/the-coding-harness.md)
3. See L1 in the parent template's `../docs/` structure (numbered domain folders + frontmatter + `.claude/hooks/`)
4. See L2 in either the parent's `../agents/` (compact) or [`sales-ops-skeleton/`](sales-ops-skeleton/) (mature)
5. See L3 in [`agent-ops-skeleton/`](agent-ops-skeleton/)

## Phase-to-file lookup

Each phase in the implementation paper maps to specific files in one
of the skeletons. Screenshot-ready for talks.

### Level 2 (from *The Coding Harness*, in [`sales-ops-skeleton/`](sales-ops-skeleton/))

| Phase | Paper says | Files to open |
|---|---|---|
| **L2-0** · Pipeline as commit chain | Twelve agents, file-based state machine, judges pull rubrics via sparse checkout, suppression as a file, git-log as audit trail | `agents/` (12 CLAUDE.md prompts), `.github/workflows/run-sales-pipeline.yml`, `.github/workflows/weekly-crawl.yml` → `dedup.yml` → `pre-filter.yml` → `enrichment.yml` → `stack-profile.yml`, `suppression/README.md` |
| **L2-1** · Judges + rubrics + golden sets | Qualifier-critic (23 criteria) + copy-evaluator (24 criteria), Cat-E hard-blocks, date-placeholder templating, verdict-flip freeze, monthly feedback loop | `agents/qualifier-critic/CLAUDE.md`, `agents/copy-evaluator/CLAUDE.md`, `evals/run_eval.py`, `evals/qualifier-critic/`, `evals/copy-evaluator/`, `.github/workflows/judge-evals.yml`, `.github/workflows/feedback-loop.yml`, `agents/feedback-loop/CLAUDE.md` |
| **L2-2** · Send-side + deliverability + kill switch | `SEQUENCES_PAUSED` autonomous flip, EU router, Attio BCC audit trail, heartbeat as absence-detector, headless execution contract | `.github/workflows/smtp-send.yml`, `.github/workflows/reply-monitor.yml`, `.github/workflows/deliverability-monitor.yml`, `.github/workflows/pipeline-heartbeat.yml`, `lib/eu_router.py`, `lib/suppression.py`, `lib/smtp_send.py`, `agents/sequence-enrollment/CLAUDE.md` |

### Level 3 (from *The Coding Harness*, in [`agent-ops-skeleton/`](agent-ops-skeleton/))

| Phase | Paper says | Files to open |
|---|---|---|
| **L3-0** · Plumbing and safety floor | Repo skeleton, attribution strip, footprint scan, heartbeat, cost ceiling, input scanner, narrow credentials (GitHub App or PAT matrix), pinned CLI | `.github/actions/strip-attribution/action.yml`, `.github/actions/setup-claude/action.yml`, `.github/workflows/footprint-scan.yml`, `.github/workflows/pipeline-heartbeat.yml`, `.github/workflows/cost-digest.yml`, `.github/workflows/budget-guard.yml`, `.github/workflows/lint.yml`, `.env.example`, `SETUP.md`, `docs/github-app-setup.md` |
| **L3-1** · Knowledge graph bootstrap | Frontmatter schema extension, mining agents, `graph.json` compilation, staleness propagation, staleness digest | `agents/dream-orchestrator/CLAUDE.md` (miner sub-prompts), `schemas/miner-findings.schema.json` |
| **L3-2** · Coding loop v1 (humans review everything) | Six-stage pipeline: intake → spec → implement → self-review (×2 fresh context) → open PR → guards | `.github/workflows/ticket-intake.yml`, `.github/workflows/spec-draft-orchestrator.yml`, `.github/workflows/spec-draft.yml`, `.github/workflows/implement.yml` (largest — carries both reviewers as separate jobs), `.github/workflows/expertise-path-guard.yml`, `state/transitions.json` + `state/README.md` (the claim state machine), `scripts/status-card.py`, `agents/plan-drafter/CLAUDE.md`, `agents/spec-drafter/CLAUDE.md`, `agents/implementer/CLAUDE.md`, `agents/pr-reviewer/CLAUDE.md`, `agents/founder-voice-pr-reviewer/CLAUDE.md`, `agents/ticket-drafter/CLAUDE.md`, `guards/example-app-core.paths`, `guards/example-app-service.paths` |
| **L3-3** · Quality gates and judges | Code-judge (Opus) scoring 0-2 across 8 categories, golden set of 20-30 historical PRs, judge-evals regression | `.github/workflows/code-judge.yml`, `.github/workflows/revise.yml` + `agents/reviser/CLAUDE.md` (the bounded loop), `.github/workflows/claim-verify.yml` + `scripts/verify-claims.py` + `agents/claim-verifier/CLAUDE.md`, `.github/workflows/judge-evals.yml`, `agents/code-judge/CLAUDE.md`, `schemas/judge-verdict.schema.json`, `evals/pr-cases/toy-fixture/`, `evals/claim-verify-cases/`, `evals/run_eval.py` |
| **L3-4** · Release intelligence | Score every released PR against ICP + messaging house, propose marketing/docs tickets, 5-dimension rubric | `.github/workflows/release-intelligence.yml`, `agents/release-intelligence-miner/CLAUDE.md`, `agents/ticket-drafter/CLAUDE.md`, `schemas/release-findings.schema.json` |
| **L3-5** · The dreaming loop | Orchestrator + three miners (transcript-failure, review-delta, doc-drift), 3× evidence bar, memory-poisoning firewall | `.github/workflows/dream.yml`, `agents/dream-orchestrator/CLAUDE.md` + miner sub-prompts, `schemas/miner-findings.schema.json` |
| **L3-6** · Earned autonomy | Autonomy ledger (L0 → L4), promotion/demotion criteria, self-improvement channel | `.github/workflows/ledger-update.yml`, `.github/workflows/metrics-digest.yml`, `schemas/autonomy-ledger.schema.json`, `state/autonomy-ledger.json` (empty seed), `.github/workflows/dependabot-triage.yml` (observe-mode maintenance loop) |

## What each skeleton ships empty

Both skeletons ship with empty state directories and defensive
`.gitignore` expansion so a downstream user can't accidentally commit
real data:

- `sales-ops-skeleton/leads/**` — all lifecycle stages ship `.gitkeep` only
- `sales-ops-skeleton/sends/queue/`, `.../log/`, `.../warmup/log/` — empty
- `sales-ops-skeleton/suppression/list.jsonl` — empty; schema documented in `suppression/README.md`
- `sales-ops-skeleton/evals/*/golden-*.json` — one hand-written toy fixture per judge; replace with your real history before enabling as a required check
- `agent-ops-skeleton/state/*.json` — empty seeds (plus small example registries: `impl-repos.json`, `dependabot-repos.json`, `failure-modes.json`)
- `agent-ops-skeleton/sessions/` — empty
- `agent-ops-skeleton/evals/pr-cases/toy-fixture/` — one hand-written toy PR; the real build wants 20-30

## Confidentiality of the ports

Both skeletons are grep-verified free of the source implementation's
company name, product name, named people, named customers, real
competitor lists, and real Slack channel IDs. See each skeleton's own
`README.md` for its "Making this real" checklist.
