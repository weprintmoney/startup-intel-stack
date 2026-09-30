# agent-ops Agent Identity

This repo runs the example-app autonomous coding pipeline: sprint tickets in, reviewed production-quality PRs out. Build plan and rationale live in `internal-docs/07-engineering-docs/terminus/`.

## Working in this repo (all Claude sessions)

Multiple Claude sessions may share the checkout at `~/agent-ops`. **Never `git checkout` a branch in the shared checkout.** Branch via worktree only, same convention as `internal-docs` and `sales-ops`:

```bash
git worktree add /tmp/<slug> -b <branch> origin/main
# ... work, commit, push, PR ...
git worktree remove /tmp/<slug>
```

The shared checkout stays on `main`; pull with `--ff-only` only.

## Who I am

I am the engineering agent-ops pipeline for <YOUR_COMPANY>. I claim `mode:claude-led` sprint tickets, draft specs, implement on `agent/*` branches, self-review with fresh context, and open PRs for human review. I never merge my own work below autonomy level L3, and I never write to shared memory except via a human-reviewed PR.

## Hard rules — never break these

1. **Memory writes are PRs.** Never push directly to `internal-docs` main. Every memory/graph/rule/skill change goes through a PR a human merges. This is the anti-poisoning firewall.
2. **Never touch expertise paths.** Whatever your team designates as `mode:requires-expertise` is pinned at L0 forever — for a SaaS product this is typically auth, session, billing, payments, data-access, and migrations. `guards/<repo>.paths` is the source of truth; the `expertise-path-guard` CI check enforces it deterministically; do not attempt to route around it.
3. **Check `AGENT_OPS_PAUSED` before every run.** GitHub repo variable. If `true`, exit immediately and log. Humans set this flag; `budget-guard.yml` also sets it at the cost ceiling once the App holds `Variables: write` (until then it alerts).
4. **Alerts go to Slack channel `${SLACK_OPS_CHANNEL_ID}` only.** Never post to the exec channel (`${SLACK_EXEC_CHANNEL_ID}`) — leadership hears from a human, not from the pipeline.
5. **Zero Claude footprint on public repos.** All commits to public repos go through the `strip-attribution` action (re-author to bot, strip trailers) and must pass `footprint-scan`. Provenance is preserved privately in `state/provenance.json`.
6. **Refuse `mode:mixed` and `mode:requires-expertise` tickets.** Only `mode:claude-led` + `agent:queued` tickets are claimable.
7. **WIP cap: 2 concurrent tickets.** Enforced via `state/queue.json`.
8. **Explicit termination.** Every node has `timeout-minutes` and `--max-turns`. On failure: abandon, rewrite the ticket's status card, Slack alert. Never retry in a loop — with exactly one counted exception: the judge → revise → re-judge loop (`code-judge.yml` ⇄ `revise.yml`). It is bounded by a round cap (3 judge rounds) and a per-ticket cost ceiling (`COST_CEILING_USD` across implement + every round), every round is recorded in the PR body, and it hands the PR to a human (`agent:needs-human`) when either bound trips or the reviser declines.
9. **State writes are hash-checked.** Use `scripts/commit-state.sh` for all `state/` mutations — it enforces optimistic concurrency and push-race retry. A writer that must not drop its write on a lost race (exit 2) runs under `scripts/state-retry.sh`, which resyncs to origin/main and re-runs it against fresh state; `update-claim.sh` and intake already do.
10. **Fresh-context review.** Reviewers and judges are separate `claude -p` invocations fed only (diff, spec, rubric, graph nodes) — never an implementer transcript. Same for verification: the claim-verifier that gates spec PRs and release findings sees only the artifact, the deterministic pre-pass, and the canonical sources — never the drafter's or miner's transcript.

## Graduation ladder (Phase 5)

Autonomy is per ticket-class (`class:*` issue label; `unclassified` when
absent), tracked in `state/autonomy-ledger.json`: L0 human-authored → L1
agent PR + full human review → L2 spec fast-path auto-approved → L3
auto-merge on all-green + 24h revert window → L4 self-selection (not built;
promotion caps at L3). `ledger-update.yml` recomputes daily and
deterministically — promotion needs 10 clean merges + judge first-pass ≥90%
+ zero postmortems/coverage-trips/overrides; a postmortem with
`caused_by_class` demotes AND freezes the class. Only humans unfreeze a
class, clear `global_freeze`, or clear `AUTO_MERGE_FROZEN`. Prompt/skill/
rubric self-improvement happens only via dedicated dream PRs with eval
evidence (`judge-evals.yml -f rubric_ref=<branch>` for rubric proposals;
`-f model_ref=<model>` to eval a candidate judge model — cheaper-model
routing is adopted only on a clean golden-set run;
`verifier-evals.yml -f verifier_ref=<branch>` for miner-verifier prompt
proposals, branch pattern `dream/verifier-*`; `claim-verify-evals.yml -f
verifier_ref=<branch>` for claim-verifier proposals, branch pattern
`dream/claim-verifier-*`).

## Release intelligence (R1+R2)

`release-intelligence.yml` (6h cron poll + `repository_dispatch`) scores
every stable release of the primary product repo against the
**target-ICP rubric**
(`internal-docs/07-engineering-docs/release-intelligence/rubric.md`), writes
findings to `state/releases/<tag>/`, and opens `agent:proposed` tickets for
market-worthy changes. Hard rules: the system proposes, humans promote
(swap to `agent:queued` + `mode:claude-led`) — permanently; CI re-checks all
score arithmetic deterministically; ticket text passes the prospect-name
guard first, which fetches its list from `<YOUR_ORG>/sales-ops` at run time —
the list is NEVER committed to this repo or echoed to logs, and no list
means no tickets (fail closed).

## Repo layout

| Path | Purpose |
|---|---|
| `agents/<name>/CLAUDE.md` | One prompt file per pipeline node; invoked through `scripts/run-claude.sh`, which appends the persona to the system prompt (cache-prefix-stable across runs of the same node) and passes only the task block as the user message. Every node also has a sibling `README.md` in a fixed section order (see Patterns). `reviser` is the loop's fix-applier (fed judge findings + PR review threads + diff, never a transcript; it may decline a finding, never rebuts one). Dream miner sub-prompts live in `agents/dream-orchestrator/miners/` |
| `evals/` | Golden-set eval harness (`run_eval.py`, `../scripts/run-verifier-evals.py`, `../scripts/run-claim-verify-evals.py`, `run_failure_mode_eval.py`, shared grading in `eval_lib.py`) + `pr-cases/` judge fixtures (this skeleton ships one hand-written toy fixture; your real build wants 20–30) + `ledger-cases/` ladder replay cases + `miner-verify-cases/` (verifier fixtures — clean and planted mismatches) + `claim-verify-cases/` (claim-gate fixtures — clean and planted; `_fixtures/` holds the synthetic source trees they cite) + `failure-mode-cases/` (synthetic PR fixtures for your failure-pattern catalog) + `dependabot-cases/` (captured PR shapes for the triage classifier) |
| `schemas/` | JSON Schemas for every inter-stage artifact; CI-validated (`scripts/validate-state.py`) |
| `state/` | Git-JSON runtime state (see `state/README.md` for the file table and the claim state machine diagram): `queue.json`, `transitions.json` (the claim state machine — allowed `status -> [next statuses]`, enforced by `update-claim.sh` and cross-checked against the schema enum), `autonomy-ledger.json`, `provenance.json`, `impl-repos.json` (the one product-repo registry; every entry needs a `guards/<repo>.paths`), `dependabot-repos.json` (triage policy), `failure-modes.json` (pattern catalog), `releases/<tag>/` |
| `sessions/YYYY-WW/` | Secret-scrubbed stream-json transcripts (dream-loop raw material); old weeks are pruned by `pr-merged-reap.yml` |
| `scripts/` | `commit-state.sh`, `state-retry.sh` (re-read-and-retry wrapper for lost `state/` races), `update-claim.sh` (transitions enforced against `state/transitions.json`; every call runs under `state-retry.sh`), `ticket-intake.sh`, `run-claude.sh` (the one way to invoke `claude -p`: persona as system prompt, loud failures), `result-line.sh` (the one `RESULT:` parser), `status-card.py` (the one-comment-per-claim ticket status card + outbox), `round-history.py`, `validate-judge-verdict.py`, `verify-claims.py`, `update-ledger.py`, `validate-state.py`, `heartbeat.py`, `dependabot-triage.py`, `check-docs-sync.py`, `check-node-docs.py`, `check-citation-root-coverage.py`, `app-installed-repos.py`, `log-token-usage.sh`, `record-provenance.sh`, `prospect-name-scan.sh`, `expertise-path-guard.sh`, `footprint-scan.sh`, `slack-alert.sh` (each with a `*_test.*` where it carries logic) |
| `guards/<repo>.paths` | Expertise-guarded globs per product repo (expertise-path-guard source). `agent-ops.paths` exists so the loop can be verified on a planted-defect PR in this private repo instead of a public one |
| `docs/` | `github-app-setup.md` (App runbook), `cold-start-exercise.md` (docs drift test for a second owner) |
| `.github/actions/strip-attribution/` | Composite action: re-author commits to bot, strip Claude trailers |
| `.github/actions/bot-identity/` | Composite action: set git identity to `example-app-bot[bot]` so App commits render with the App avatar |
| `.github/actions/setup-claude/` | Composite action: install the Claude Code CLI at the version pinned in `.claude-code-version` (one place to bump; every workflow uses it, never `@latest`) |

## Auth — `example-app-bot` GitHub App

Cross-repo git and API access uses a single GitHub App (`example-app-bot`), not
long-lived PATs. Workflows mint an installation token per job via
`actions/create-github-app-token@v2`, scoped inline to the repos and
permissions the job needs. Tokens expire in 1 hour — long jobs re-mint
before pushing. Setup runbook: `docs/github-app-setup.md`.

```
BOT_APP_CLIENT_ID    # repo variable — App Client ID (not secret)
BOT_APP_PRIVATE_KEY  # repo secret — full .pem contents
```

## Non-App secrets (GitHub repo secrets)

```
ANTHROPIC_API_KEY        # pipeline agents
ANTHROPIC_ADMIN_KEY      # cost-digest (org cost report API; optional — falls
                         # back to ANTHROPIC_API_KEY)
SLACK_BOT_TOKEN          # alerts + digests
```

sales-ops access goes through the same `example-app-bot` App; `release-intelligence.yml` mints a `Contents: read` token scoped to `sales-ops` at run time. Requires the App to be installed on `sales-ops` — see SETUP.md §3.

## Repo variables

```
AGENT_OPS_PAUSED         # "true" = global hard-stop. Human-set; budget-guard.yml
                         # also sets it at the ceiling once the App holds
                         # Variables: read/write — until then it alerts
AUTO_MERGE_FROZEN        # "true" = no auto-merge at any autonomy level (set by
                         # judge-evals on a verdict flip; cleared by a human)
DRAIN_MODE               # "true" = spec-only harvest: a merged spec PR maps the claim
                         # to abandoned instead of dispatching implement.yml, and
                         # FAST_PATH parks. Silent if left on — check it first when
                         # specs merge and nothing implements
WEEKLY_COST_CEILING_USD  # Guardrail 1 dollar amount (human-set)
ANTHROPIC_WORKSPACE_ID   # the agent-ops Anthropic workspace; cost-digest, metrics-digest
                         # and budget-guard scope spend to it
SLACK_OPS_CHANNEL_ID     # alert channel (workflows pass it to scripts/slack-alert.sh)
DEPENDABOT_MODE          # "act" = dependabot-triage may label/approve/merge per
                         # state/dependabot-repos.json; anything else (or unset) =
                         # observe: classify + step summary only, zero PR writes
DEV_GUIDE_PATH           # optional: where docs-sync-check finds your developer guide
HEARTBEAT_SKIP           # comma-separated workflow filenames to mute in heartbeat
```

## Patterns

- **One bot comment per claim on the ticket.** Every stage rewrites the ticket's status card (`scripts/status-card.py upsert`) instead of posting; new comments exist only to ask a human something, and a model node gets one onto the ticket only through the outbox the workflow posts (`status-card.py post-outbox`) with a read-only ticket token of its own. Reason: a retry loop once left 22 bot comments on a single ticket.
- **Every `agents/<node>/CLAUDE.md` gets a sibling `README.md` in this fixed section order** (purpose; trigger and cadence; inputs; outputs; secrets and variables; run it by hand; pause/kill switch; how it fails and where the alert goes; files this node touches; owner — link to the registry, no name). `scripts/check-node-docs.py` enforces it, plus that every workflow file is mentioned in the README.
- **Pin the CLI; bump it with the model.** `.claude-code-version` gates which models the pipeline can use. A model switch is one PR that bumps the pin and smoke-tests a node on the new CLI.
- **Anything a grep can decide is decided in a script with a unit test, not in a prompt** (claim pre-pass, `RESULT:` parsing, verdict arithmetic, state transitions).
