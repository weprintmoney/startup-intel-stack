# agent-ops skeleton

A worked example of **Level 3 — the coding harness** from
[*The Coding Harness*](../../docs/00-foundations/the-coding-harness.md).

Sprint tickets in → reviewed, production-quality PRs out. The pipeline is
GitHub Actions all the way down. The model decides only *within* a node,
never the pipeline's next step.

This is a template. All company-specific values are `<YOUR_ORG>`,
`<YOUR_COMPANY>`, `<FOUNDER_NAME>`, `<ENG_LEAD_NAME>`, or `${SLACK_*}`
placeholders. See "Making this real" below.

---

## What's in here

The file surface is the same as a real Phase 0–6 build. What runs against
what changes with your product; the shape doesn't.

| Path | What it is |
|---|---|
| `agents/<name>/CLAUDE.md` | One prompt per pipeline node. Invoked as `claude -p "$(cat agents/<name>/CLAUDE.md)"` |
| `agents/dream-orchestrator/miners/` | Sub-prompts spawned as parallel Task-tool subagents |
| `agents/founder-voice-pr-reviewer/` | Founder-voice fresh-context reviewer. Rewrite this in your founder's voice before enabling it |
| `.github/workflows/` | Every stage as a workflow. `ticket-intake`, `spec-draft`, `implement`, `code-judge`, `judge-evals`, `dream`, `ledger-update`, `metrics-digest`, `release-intelligence`, `expertise-path-guard`, `footprint-scan`, `cost-digest`, `pipeline-heartbeat`, `schema-validate` |
| `.github/actions/strip-attribution/` | Composite action: re-author commits to a bot, strip Claude trailers. Used before every public-repo PR opens |
| `schemas/` | JSON Schemas for every inter-stage artifact. CI validates on every merge |
| `evals/pr-cases/` | Golden-set fixtures — historical PRs with known human verdicts. This skeleton ships one hand-written toy fixture; your real build will have 20–30 |
| `evals/run_eval.py` | Harness that replays fixtures through the judges and compares against `expected.json` |
| `guards/<repo>.paths` | Expertise-path globs per product repo. `expertise-path-guard.yml` blocks agent PRs touching these |
| `state/` | Git-JSON runtime state: `queue.json`, `autonomy-ledger.json`, `provenance.json`, and `releases/<tag>/` |
| `scripts/` | State-write action (hash-check + rebase retry), Slack alert, footprint scan, path guard, ledger recompute |
| `sessions/YYYY-WW/` | Condensed, secret-scrubbed transcripts. Dream-loop input |

## How this maps to the paper

Read [`../../docs/00-foundations/the-coding-harness.md`](../../docs/00-foundations/the-coding-harness.md)
first if you haven't. This skeleton lays out one node per paper phase.

| Paper phase | This skeleton |
|---|---|
| L3-0 Plumbing + safety floor | `.github/actions/strip-attribution/`, `scripts/footprint-scan.sh`, `.github/workflows/pipeline-heartbeat.yml`, `.github/workflows/cost-digest.yml`, `.github/workflows/schema-validate.yml`, `scripts/commit-state.sh`, `state/provenance.json` |
| L3-1 Knowledge graph bootstrap | Lives in your `internal-docs` repo — no code here. See [`context-loops-graphs.md`](../../docs/00-foundations/context-loops-graphs.md) L1-1 |
| L3-2 Coding loop v1 | `.github/workflows/ticket-intake.yml`, `spec-draft.yml`, `implement.yml`; `agents/{implementer,spec-drafter,pr-reviewer,founder-voice-pr-reviewer,ticket-drafter}/` |
| L3-3 Quality gates + judges | `.github/workflows/code-judge.yml`, `judge-evals.yml`; `agents/code-judge/`; `evals/pr-cases/`; `schemas/judge-verdict.schema.json` |
| L3-4 Release intelligence | `.github/workflows/release-intelligence.yml`; `agents/release-intelligence-miner/`; `schemas/release-findings.schema.json`; `scripts/validate-release-findings.py` |
| L3-5 Dreaming loop | `.github/workflows/dream.yml`; `agents/dream-orchestrator/` + `miners/`; `schemas/miner-findings.schema.json` |
| L3-6 Earned autonomy | `.github/workflows/ledger-update.yml`, `metrics-digest.yml`; `scripts/update-ledger.py`; `state/autonomy-ledger.json`; `schemas/autonomy-ledger.schema.json`; `evals/ledger-cases/` (replay fixtures — none ship in this skeleton) |

## The coding loop, in flow

```
human labels ticket agent:queued (+ mode:claude-led)
  → ticket-intake.yml   deterministic; refuses mixed/requires-expertise,
                        WIP cap 2, claims into state/queue.json
  → spec-draft.yml      7-section spec PR to internal-docs (human approves),
                        or fast path (bug-fix / contract-preserving refactor
                        / docs-only): intent note + straight to ↓
  → implement.yml       human dispatches after spec merges. Jobs:
                        implement → 2 parallel fresh-context reviews
                        (generic Sonnet + founder-voice Opus, fed only
                        diff + spec + ticket) → address/rebut findings →
                        PR with both reviews attached → Slack notify
```

Failure contract at every stage: claim abandoned, issue comment, Slack
alert. The `agent/<issue>-<slug>` branch survives as a checkpoint. The
`AGENT_OPS_PAUSED=true` repo variable stops intake/spec/implement globally
(the cost-digest sets this on ceiling breach).

## Making this real

This skeleton runs no-op — every workflow gates on secrets that don't exist
yet. To land it in your org:

1. **Replace the placeholders.** Search the tree for `<YOUR_ORG>`,
   `<YOUR_COMPANY>`, `<FOUNDER_NAME>`, `<ENG_LEAD_NAME>`, and every
   `example-app-*` repo name. Substitute your real values.
2. **Provision the bot account and PATs.** See [`SETUP.md`](SETUP.md).
   Never give an agent a token scoped beyond one PR.
3. **Fill `.env.example` and copy to `.env`.** The workflows read the
   secrets by name; the file documents what each is for.
4. **Rewrite `guards/*.paths` with your real crown-jewel code areas.**
   The stubs list a plausible SaaS shape (billing, auth, session,
   payments, migrations, public APIs, webhooks, data-access). Yours will
   look different. If your reviewer says "this file is off-limits to
   junior engineers," it belongs in the guard.
5. **Rewrite `agents/founder-voice-pr-reviewer/CLAUDE.md`** in your actual
   founder's voice. The starter has the pattern (terse, imperative, no
   softeners) but the domain checklist and few-shot examples must come
   from you. Grab 20–40 real founder review comments and encode them.
6. **Build your golden set.** Replace `evals/pr-cases/toy-fixture/` with
   20–30 historical PRs from your product repos, one directory each with
   `spec.md`, `diff.patch`, `context.md`, `expected.json`. This is what
   the judge is measured against.
7. **Adapt agent prompts to your stack.** The `implementer`, `pr-reviewer`,
   `code-judge`, and `spec-drafter` prompts assume a general stack; add
   the QA skills, language rules, and layering conventions that your team
   actually reviews for.

Do not enable auto-merge (Phase 5 / L3-6) until the golden set is stable
and the judge has been running as an advisory check for at least two
sprints. The paper is clear about the readiness gate — respect it.

## Layout

```
agents/            one CLAUDE.md prompt per pipeline node
                   (+ dream miner prompts under dream-orchestrator/miners/)
evals/             run_eval.py + pr-cases/ (golden fixtures)
guards/            <repo>.paths expertise-guarded globs per product repo
schemas/           JSON Schemas for inter-stage artifacts + fixtures
state/             git-JSON runtime state (hash-checked writes via
                   scripts/commit-state.sh)
sessions/YYYY-WW/  condensed, secret-scrubbed transcripts (dream input)
scripts/           commit-state.sh, update-claim.sh, ticket-intake.sh,
                   update-ledger.py, validate-release-findings.py,
                   prospect-name-scan.sh, expertise-path-guard.sh (+ test),
                   footprint-scan.sh, slack-alert.sh
.github/
  workflows/       pipeline-heartbeat, cost-digest, schema-validate,
                   ticket-intake, spec-draft, implement, code-judge,
                   judge-evals, dream, ledger-update, metrics-digest,
                   release-intelligence, expertise-path-guard,
                   footprint-scan
  actions/strip-attribution/   re-author commits to bot, strip Claude trailers
```

## Reading order

1. [`../../docs/00-foundations/the-coding-harness.md`](../../docs/00-foundations/the-coding-harness.md) — the paper.
2. [`../../docs/00-foundations/context-loops-graphs.md`](../../docs/00-foundations/context-loops-graphs.md) — the prerequisite framework.
3. [`SETUP.md`](SETUP.md) — the human-action checklist.
4. [`CLAUDE.md`](CLAUDE.md) — hard rules the pipeline enforces.
5. Then walk the workflows in `.github/workflows/` alongside the paper's L3-0 through L3-6 sections.
