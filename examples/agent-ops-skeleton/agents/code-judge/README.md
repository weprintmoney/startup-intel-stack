# code-judge

## Purpose

Fresh-context Opus invocation that scores an agent-opened PR's diff against the code-judge rubric (`internal-docs/07-engineering-docs/code-judge-rubric.md`, 20 criteria + 5 blocking findings). It is the Phase 3 quality gate between an agent PR opening and human review — the first counted round of the bounded judge -> revise -> re-judge loop.

## Trigger and cadence

`workflow_dispatch` only, no cron. Dispatched by `implement.yml`'s `open-pr` job right after the PR opens (`round=1`), and re-dispatched by `revise.yml`'s "Dispatch code-judge (next round)" step after each revision (`round=N+1`). Concurrency-serialized per PR (`group: code-judge-${{ inputs.repo }}-${{ inputs.pr }}`). Regression-tested (not invoked in production) by `judge-evals.yml` (`eval` job, matrix includes `code-judge`; PRs touching `agents/code-judge/**`, weekly Monday 11:00 UTC cron, dispatch) against 27 historical PRs in `evals/pr-cases/`, and by `failure-mode-evals.yml` (same matrix; weekly Wednesday 11:00 UTC cron) against the synthetic failure-mode fixtures in `evals/failure-mode-cases/`.

## Inputs

- Dispatch inputs: `pr`, `issue` (optional), `repo` (default `example-app-core`), `round` (optional — derived from the PR body's round block if omitted)
- `internal-docs/07-engineering-docs/code-judge-rubric.md` — the rubric, read-only checkout
- `/tmp/review-input/diff.patch` — `gh pr diff` on the PR
- `/tmp/review-input/context.md` — PR title + body
- `/tmp/review-input/ticket.json` — the source issue (title, body, labels), when `issue` is given
- `/tmp/review-input/run-meta.json` — `repo`, `pr`, `rubric_version`, `run_url`
- `state/failure-modes.json` — the catalogued failure patterns the judge cites by ID when a criterion fails on one

## Outputs

- `/tmp/review-output/verdict.json` (`schemas/judge-verdict.schema.json`) and `/tmp/review-output/findings.md`
- Commit status `agent-ops/code-judge` on the product-repo PR head
- A findings comment on the PR (synthesized from what exists if `findings.md` is missing)
- The round appended to the PR body's round block (`scripts/round-history.py`)
- Label `agent:judge-pass` (score >=80, no blocking findings) or `agent:needs-human` (cap/ceiling reached)
- On judge-pass at autonomy L3+ with `AUTO_MERGE_FROZEN` unset and an issue linked: auto-merge armed (24h revert window)

## Secrets and variables

`ANTHROPIC_API_KEY`, `BOT_APP_PRIVATE_KEY`, `BOT_APP_CLIENT_ID` (variable), `ANTHROPIC_WORKSPACE_ID` (variable, via `ANTHROPIC_CUSTOM_HEADERS`), `SLACK_BOT_TOKEN`. Gated on `vars.AGENT_OPS_PAUSED != 'true'`; the auto-merge step additionally checks `vars.AUTO_MERGE_FROZEN != 'true'`.

## Run it by hand

```bash
gh workflow run code-judge.yml -f pr=<n> -f repo=<impl-repo> [-f issue=<n>] [-f round=<n>]
```
Leaving `round` empty re-derives it from the PR body's round block — the right call for a manual re-judge after new commits.

## Pause / kill switch

`AGENT_OPS_PAUSED=true` skips the whole job. Separately, `code-judge` is the entry point to CLAUDE.md hard rule 8's round-cap/cost-ceiling loop with `reviser`: `ROUND_CAP=3`, `COST_CEILING_USD=50` per ticket, tracked via `scripts/round-history.py` in the PR body. `decide` there returns `judge-pass`, `revise`, `needs-human:cap`, or `needs-human:cost` — every exit lands on a human once the cap or ceiling is hit. `AUTO_MERGE_FROZEN=true` blocks only the auto-merge step, not the judge run itself.

## How it fails and where the alert goes

A missing or schema/arithmetic-invalid `verdict.json` (checked by `scripts/validate-judge-verdict.py`, never the model's own words) posts a `failure` commit status with the rejection reason and fails the run at the end — this is a *rejected verdict*, distinct from a legitimate `fail` score, and the loop halts (`decide` returns `halt:rejected-verdict`) rather than dispatching `revise`. Per the root README: "A judge *run* failure never blocks the PR — it alerts Slack" (`README.md:100`) — the "Alert on failure" step posts `:x: code-judge run failed for $IMPL_REPO PR #... (the PR is NOT blocked — no status posted)` to `${SLACK_OPS_CHANNEL_ID}`, suppressed if `scripts/is-systemic-failure.sh` flags it as infra-wide. A genuine judge pass/fail (valid verdict) instead posts `:white_check_mark: code-judge PASS ...` or, at the round cap/cost ceiling, `:raised_hand: code-judge FAIL on round $ROUND and the loop stopped ...` with the full round history, both to `${SLACK_OPS_CHANNEL_ID}`.

## Files this node touches

`agents/code-judge/CLAUDE.md`, `.github/workflows/code-judge.yml`, `.github/workflows/judge-evals.yml`, `.github/workflows/failure-mode-evals.yml`, `internal-docs/07-engineering-docs/code-judge-rubric.md`, `schemas/judge-verdict.schema.json`, `scripts/validate-judge-verdict.py`, `scripts/round-history.py`, `scripts/result-line.sh`, `scripts/slack-alert.sh`, `scripts/is-systemic-failure.sh`, `state/failure-modes.json`, `state/autonomy-ledger.json` (auto-merge level check), `evals/pr-cases/`, `evals/failure-mode-cases/`.

## Owner

See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
