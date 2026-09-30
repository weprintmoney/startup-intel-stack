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
| `.github/workflows/` | Every stage as a workflow. The loop: `ticket-intake`, `spec-draft-orchestrator`, `spec-draft`, `claim-verify`, `spec-pending-reap`, `implement`, `code-judge`, `revise`, `pr-review-reap`, `pr-merged-reap`. The gates: `expertise-path-guard`, `footprint-scan`, `lint`, `schema-validate`. Learning and autonomy: `dream`, `release-intelligence`, `ledger-update`, `metrics-digest`. Evals: `judge-evals`, `judge-evals-repeat`, `claim-verify-evals`, `verifier-evals`, `failure-mode-evals`. Ops: `cost-digest`, `budget-guard`, `pipeline-heartbeat`, `install-preflight`, `docs-sync-check`, `dependabot-triage` |
| `.github/actions/strip-attribution/` | Composite action: re-author commits to a bot, strip Claude trailers. Used before every public-repo PR opens |
| `.github/actions/bot-identity/`, `setup-claude/` | Composite actions: App git identity, and the pinned Claude Code CLI install (`.claude-code-version` — one place to bump) |
| `schemas/` | JSON Schemas for every inter-stage artifact. CI validates on every merge (`scripts/validate-state.py`) |
| `evals/claim-verify-cases/`, `miner-verify-cases/`, `failure-mode-cases/`, `dependabot-cases/`, `ledger-cases/` | Golden sets for the claim-verify gate, the dream verifiers, the failure-pattern catalog, the Dependabot classifier, and the autonomy ladder. The skeleton ships small synthetic sets; the harnesses are the point |
| `evals/pr-cases/` | Golden-set fixtures — historical PRs with known human verdicts. This skeleton ships one hand-written toy fixture; your real build will have 20–30 |
| `evals/run_eval.py` | Harness that replays fixtures through the judges and compares against `expected.json` |
| `guards/<repo>.paths` | Expertise-path globs per product repo (plus `agent-ops.paths`, so the loop can be verified on a planted-defect PR here). `expertise-path-guard.yml` blocks agent PRs touching these |
| `docs/` | [`github-app-setup.md`](docs/github-app-setup.md) (the App replaces the PAT matrix), [`cold-start-exercise.md`](docs/cold-start-exercise.md) (a docs-drift test for a prospective second owner) |
| `state/` | Git-JSON runtime state: `queue.json`, `transitions.json` (the claim state machine), `autonomy-ledger.json`, `provenance.json`, `impl-repos.json`, `dependabot-repos.json`, `failure-modes.json`, and `releases/<tag>/`. See [`state/README.md`](state/README.md) |
| `scripts/` | State-write action (hash-check + rebase retry + `state-retry.sh`), the one `claude -p` wrapper (`run-claude.sh`) and `RESULT:` parser, status card, claim verifier, Slack alert, footprint scan, path guard, ledger recompute, Dependabot classifier. Anything a grep can decide lives here with a `*_test.*` |
| `sessions/YYYY-WW/` | Condensed, secret-scrubbed transcripts. Dream-loop input |

## How this maps to the paper

Read [`../../docs/00-foundations/the-coding-harness.md`](../../docs/00-foundations/the-coding-harness.md)
first if you haven't. This skeleton lays out one node per paper phase.

| Paper phase | This skeleton |
|---|---|
| L3-0 Plumbing + safety floor | `.github/actions/strip-attribution/`, `scripts/footprint-scan.sh`, `.github/workflows/pipeline-heartbeat.yml`, `.github/workflows/cost-digest.yml`, `budget-guard.yml`, `lint.yml`, `install-preflight.yml`, `.github/workflows/schema-validate.yml`, `scripts/commit-state.sh`, `state/provenance.json` |
| L3-1 Knowledge graph bootstrap | Lives in your `internal-docs` repo — no code here. See [`context-loops-graphs.md`](../../docs/00-foundations/context-loops-graphs.md) L1-1 |
| L3-2 Coding loop v1 | `.github/workflows/ticket-intake.yml`, `spec-draft-orchestrator.yml`, `spec-draft.yml`, `spec-pending-reap.yml`, `implement.yml`; `agents/{plan-drafter,implementer,spec-drafter,pr-reviewer,founder-voice-pr-reviewer,ticket-drafter}/`; `scripts/status-card.py`, `scripts/update-claim.sh` + `state/transitions.json` |
| L3-3 Quality gates + judges | `.github/workflows/code-judge.yml`, `revise.yml`, `pr-review-reap.yml`, `claim-verify.yml`, `judge-evals.yml`, `judge-evals-repeat.yml`, `claim-verify-evals.yml`, `failure-mode-evals.yml`; `agents/{code-judge,reviser,claim-verifier}/`; `evals/`; `schemas/{judge-verdict,claim-verdict}.schema.json` |
| L3-4 Release intelligence | `.github/workflows/release-intelligence.yml`; `agents/release-intelligence-miner/`; `schemas/release-findings.schema.json`; `scripts/validate-release-findings.py` |
| L3-5 Dreaming loop | `.github/workflows/dream.yml`, `verifier-evals.yml`; `agents/dream-orchestrator/` + `miners/`, `agents/miner-verifier/`; `schemas/miner-findings.schema.json` |
| L3-6 Earned autonomy | `.github/workflows/ledger-update.yml`, `metrics-digest.yml`, `dependabot-triage.yml`; `scripts/update-ledger.py`; `state/autonomy-ledger.json`; `schemas/autonomy-ledger.schema.json`; `evals/ledger-cases/` (ladder replay fixtures) |

## The coding loop, in flow

```
human labels ticket agent:queued (+ mode:claude-led, + repo:<name>)
  → ticket-intake.yml   deterministic; refuses mixed/requires-expertise,
                        WIP cap, one claim per (issue, impl_repo) in
                        state/queue.json
  → spec-draft-orchestrator.yml
                        dispatches one spec-draft per claimed ticket, in
                        parallel, and re-runs on every completion
  → spec-draft.yml      7-section spec PR to internal-docs (human approves),
                        or fast path (bug-fix / contract-preserving refactor
                        / docs-only): intent note + straight to ↓.
                        Runs spec-lint on its own output, then the
                        claim-verify gate (below) before the PR opens
  → spec-pending-reap   cron poll: merging the spec PR IS the approval act;
                        closing it unmerged abandons the claim
  → implement.yml       plan (plan.md + spec.md, acceptance criteria copied
                        verbatim as `- [ ]`) → implement (works the checklist;
                        the job fails while any `- [ ]` remains) → 2 parallel
                        fresh-context reviews (generic Sonnet + founder-voice
                        Opus, fed only diff + spec + ticket) → address/rebut
                        findings → PR with both reviews attached → Slack notify
  → code-judge.yml ⇄ revise.yml
                        bounded judge → revise → re-judge loop (below)
  → pr-review-reap      a human "changes requested" on an agent PR dispatches
                        a revision round
  → pr-merged-reap      merged PR → claim `merged`; old claims and session
                        weeks are pruned
```

Every claim moves only along an edge in [`state/transitions.json`](state/transitions.json)
— see the state machine diagram in [`state/README.md`](state/README.md).
`scripts/update-claim.sh` refuses any illegal edge at write time, and
`scripts/validate-state.py` cross-checks the table against the schema enum so
the two cannot drift.

**Ticket status card.** A claim gets exactly one bot comment on its ticket:
intake creates it, every later stage rewrites it in place (links, retry
count, collapsed run history). One card per (ticket, implementation repo).
New comments are reserved for a human being asked something: the drafter
writes them to an outbox and the workflow posts only the allowed kinds
(`scripts/status-card.py post-outbox`) — the drafter's own ticket token is
read-only. `state/queue.json` remains the state of record; the card is a
projection.

**Spec-draft outcomes.** The drafter closes the questions it can answer from
source and routes the rest:

| `RESULT:` | When | What the workflow does |
|---|---|---|
| `SPEC_PR <url>` | normal | claim → `spec-pending` |
| `FAST_PATH` | template's does-not-apply list | claim → `spec-approved`, implement dispatched |
| `GROOMING_BLOCKER <reason>` | ticket contradicts itself or the source it cites | claim abandoned, ticket handed back to grooming |
| `CLARIFY_NEEDED <reason>` | one scope boundary is undecidable | claim → `spec-clarify-pending` (parked, no WIP slot) until a human answers |
| `DEPENDENCY_BLOCKED <ref>` | a named prerequisite hasn't landed | claim abandoned with `blocked_by`; re-queue when `<ref>` lands |
| `UNFIT <reason>` | touches expertise-guarded paths | claim abandoned, re-triage requested |

Named-person asks are @-mentioned only through the closed list in
`agents/spec-drafter/named-people.yaml` — never a guessed handle.

**Bounded judge → revise → re-judge loop.** `code-judge.yml` scores the PR; on
`fail`, `revise.yml` runs the `reviser` (judge findings + PR review threads +
diff, never a transcript; it may decline a finding) and re-dispatches the
judge. The loop stops at a round cap (3) or a per-ticket cost ceiling
(`COST_CEILING_USD`, summed from every node's own cost estimate), records
each round in the PR body, and hands the PR to a human (`agent:needs-human`)
when either bound trips. It is the one counted exception to "never retry in a
loop" (CLAUDE.md rule 8). The judge's verdict arithmetic is recomputed
deterministically in CI (`scripts/validate-judge-verdict.py`) — the model's
score is never trusted alone.

**Claim-verify gate.** Agents that write prose about the product can be
right-shaped and wrong. `claim-verify.yml` runs a deterministic pre-pass
(`scripts/verify-claims.py`: retired phrases, cited `path:line` that do not
exist, missing graph nodes, evidence outside your org, version tags against
the changelog) and then a fresh-context `claim-verifier` that sees only the
artifact, the pre-pass claims, and the canonical sources. A material
contradiction converts the spec PR to draft and labels it
`claims:contradicted`; a contradiction the verifier marks `material: false`
(a line count off by two) flags instead of blocking. A golden set in
`evals/claim-verify-cases/` tests the gate itself, including one case per
citation root.

**Cost ceiling that enforces.** `cost-digest.yml` reports spend;
`budget-guard.yml` checks trailing-7-day spend for the pipeline's Anthropic
workspace every 15 minutes and, when the App holds `Variables: write`, sets
`AGENT_OPS_PAUSED=true` the moment `WEEKLY_COST_CEILING_USD` is crossed
(until then it alerts). Eval suites are path-filtered and cancel stacked runs
so a PR under iteration cannot burn the week's budget.

**Dependabot triage.** `dependabot-triage.yml` classifies every open
Dependabot PR against `state/dependabot-repos.json` (verify checks are an
allowlist), and in `act` mode merges green minor/patch bumps and hands majors
to a rotating reviewer. The default is observe mode: classify and summarize,
zero PR writes. Everything a regex or status lookup can decide lives in
`scripts/dependabot-triage.py` with a unit test; the model is never in the
merge path.

Failure contract at every stage: claim abandoned, the ticket's status card
rewritten, Slack alert. The `agent/<issue>-<slug>` branch survives as a
checkpoint, so re-dispatch resumes. The `AGENT_OPS_PAUSED=true` repo variable
stops intake/spec/implement globally.

## Making this real

This skeleton runs no-op — every workflow gates on secrets that don't exist
yet. To land it in your org:

1. **Replace the placeholders.** Search the tree for `<YOUR_ORG>`,
   `<YOUR_COMPANY>`, `<FOUNDER_NAME>`, `<ENG_LEAD_NAME>`, every
   `example-app-*` repo name, and `example-org` (the valid-URL placeholder used
   inside schemas, fixtures, and test data — also set `GITHUB_ORG` for the
   claim verifier). Replace `agents/spec-drafter/named-people.yaml` with your
   real team. Substitute your real values.
2. **Create the GitHub App.** See [`SETUP.md`](SETUP.md) and
   [`docs/github-app-setup.md`](docs/github-app-setup.md). Never give an
   agent a token scoped beyond one job.
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
agents/            one CLAUDE.md prompt + README.md per pipeline node
                   (+ dream miner prompts under dream-orchestrator/miners/)
docs/              github-app-setup.md, cold-start-exercise.md
evals/             run_eval.py, eval_lib.py, run_failure_mode_eval.py and
                   the golden sets: pr-cases/, claim-verify-cases/,
                   miner-verify-cases/, failure-mode-cases/,
                   dependabot-cases/, ledger-cases/
guards/            <repo>.paths expertise-guarded globs per product repo
                   (+ agent-ops.paths for the loop-verification sandbox)
schemas/           JSON Schemas for inter-stage artifacts + fixtures
state/             git-JSON runtime state (hash-checked writes via
                   scripts/commit-state.sh); README.md has the state machine
sessions/YYYY-WW/  condensed, secret-scrubbed transcripts (dream input)
scripts/           commit-state.sh, state-retry.sh, update-claim.sh,
                   ticket-intake.sh, run-claude.sh, result-line.sh,
                   status-card.py, round-history.py, verify-claims.py,
                   validate-state.py, validate-judge-verdict.py,
                   heartbeat.py, dependabot-triage.py, update-ledger.py,
                   footprint-scan.sh, expertise-path-guard.sh (+ tests),
                   slack-alert.sh, ... (each with a *_test.* where it
                   carries logic)
.claude-code-version   the pinned Claude Code CLI every workflow installs
.github/
  workflows/       budget-guard.yml, claim-verify-evals.yml,
                   claim-verify.yml, code-judge.yml, cost-digest.yml,
                   dependabot-triage.yml, docs-sync-check.yml, dream.yml,
                   expertise-path-guard.yml, failure-mode-evals.yml,
                   footprint-scan.yml, implement.yml,
                   install-preflight.yml, judge-evals-repeat.yml,
                   judge-evals.yml, ledger-update.yml, lint.yml,
                   metrics-digest.yml, pipeline-heartbeat.yml,
                   pr-merged-reap.yml, pr-review-reap.yml,
                   release-intelligence.yml, revise.yml,
                   schema-validate.yml, spec-draft-orchestrator.yml,
                   spec-draft.yml, spec-pending-reap.yml,
                   ticket-intake.yml, verifier-evals.yml
  actions/         strip-attribution, bot-identity, setup-claude
```

## Reading order

1. [`../../docs/00-foundations/the-coding-harness.md`](../../docs/00-foundations/the-coding-harness.md) — the paper.
2. [`../../docs/00-foundations/context-loops-graphs.md`](../../docs/00-foundations/context-loops-graphs.md) — the prerequisite framework.
3. [`SETUP.md`](SETUP.md) — the human-action checklist, and [`state/README.md`](state/README.md) — the claim state machine.
4. [`CLAUDE.md`](CLAUDE.md) — hard rules the pipeline enforces.
5. Then walk the workflows in `.github/workflows/` alongside the paper's L3-0 through L3-6 sections.
