# plan-drafter

## Purpose

Turns an approved spec (or fast-path intent note) into `plan.md` — a checklist of implementation steps and verbatim acceptance criteria the executor mechanically cannot skip. Stage 3a of the coding loop, running before the implementer; it never writes product code.

## Trigger and cadence

No trigger of its own — it is the `plan` job inside `.github/workflows/implement.yml`, one of five jobs in that workflow's `workflow_dispatch`. Inputs: `issue` (product-repo issue number), `branch` (`agent/<issue>-<slug>`), `repo` (implementation repo, default `example-app-core`). Concurrency group `implement-${{ inputs.issue }}` (`cancel-in-progress: false`) serializes re-runs per ticket. Dispatching `implement.yml` is the human-approval act for a pending spec.

## Inputs

- The ticket (`gh issue view`, `TICKET_REPO=<YOUR_ORG>/example-app-core`)
- `SPEC_PATH` — looked up from `state/queue.json` (`.claims[]` matching issue + impl_repo); empty on the fast path, where the intent note lives in the issue comments instead
- `./product/` — the implementation repo, `BRANCH` checked out (created fresh or resumed)
- `./internal-docs/` — read-only checkout of `internal-docs` (spec, graph nodes, `terminus/invariants.md`, `terminus/performance-budgets.md`)
- `./guards/<repo>.paths` — expertise-guarded globs for the target repo

## Outputs

- `./product/plan.md` (Implementation steps / Acceptance criteria / Files expected to change / Constraints) and `./product/spec.md` (spec or intent note, copied verbatim); `.gitignore` gets a one-line append for both if missing
- Committed to `BRANCH` and pushed (`plan: draft implementation checklist for #<issue>`) — skipped as a no-op if `plan.md` already exists on the branch (resume path)
- `RESULT: PLANNED` or `RESULT: BLOCKED <reason>`, read by `scripts/result-line.sh`

## Secrets and variables

`ANTHROPIC_API_KEY`, `BOT_APP_PRIVATE_KEY` + repo variable `BOT_APP_CLIENT_ID` (mint the product-repo and internal-docs tokens), repo variable `ANTHROPIC_WORKSPACE_ID` (custom header). Repo variable `AGENT_OPS_PAUSED` gates the job directly (`if: vars.AGENT_OPS_PAUSED != 'true'`); a separate in-job "Gate on required secrets" step no-ops (not a failure) if `ANTHROPIC_API_KEY`, `BOT_APP_PRIVATE_KEY`, or `BOT_APP_CLIENT_ID` is missing.

## Run it by hand

Not dispatchable standalone — it is the `plan` job inside `implement.yml`, not its own workflow. Dispatch the whole pipeline:
```bash
gh workflow run implement.yml -f issue=<n> -f branch=agent/<n>-<slug> -f repo=<impl-repo>
```
Re-dispatching with the same branch is also how a stalled plan resumes: if `plan.md` is already on the branch, this stage is skipped.

## Pause / kill switch

`AGENT_OPS_PAUSED=true` skips the `plan` job's `if:` outright, which also skips every downstream job (they all key off `needs.plan.outputs.go`). Missing secrets degrade the same way but silently — job succeeds, `go=false`, no alert.

## How it fails and where the alert goes

A genuine failure (bad `RESULT`, a write outside `plan.md`/`spec.md`/`.gitignore` caught by "Enforce plan-pass write scope", a missing `plan.md`/`spec.md`) fails the job. The shared `alert-on-failure` job (`needs: [plan, implement, review-generic, review-founder-voice, open-pr]`, `if: failure() && needs.plan.outputs.go == 'true'`) then abandons the claim (`scripts/update-claim.sh ... abandoned`), comments on the product-repo issue, and posts to Slack channel `${SLACK_OPS_CHANNEL_ID}` via `scripts/slack-alert.sh`: `:x: implement pipeline failed for $TICKET_REPO#$ISSUE ($IMPL_REPO) — claim abandoned, branch $BRANCH kept. $RUN_URL`. A soft no-op (paused, or missing secrets) produces only a log line — no failure, no Slack alert.

## Files this node touches

`agents/plan-drafter/CLAUDE.md`, `.github/workflows/implement.yml` (`plan` job), `.github/actions/bot-identity`, `.github/actions/setup-claude`, `scripts/run-claude.sh`, `scripts/result-line.sh`, `scripts/log-token-usage.sh`, `state/queue.json` (`SPEC_PATH` lookup), `schemas/queue-claim.schema.json`, `guards/<repo>.paths`.

## Owner
See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
