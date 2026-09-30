# reviser

## Purpose

Fresh-context Sonnet invocation that fixes what it can of a failed `code-judge` verdict on an open agent PR — findings, human/bot PR review threads, and prior rounds, but never the implementer's or an earlier reviser's transcript. It is the "revise" half of the bounded judge -> revise -> re-judge loop; it may decline a finding but never rebuts one.

## Trigger and cadence

`workflow_dispatch` only, no cron. Dispatched by `code-judge.yml`'s "Loop — dispatch revise" step when the verdict is `fail`, the round is under the cap, and the ticket is under its cost ceiling (job: `judge`, decision `revise`). Concurrency-serialized per PR (`group: revise-${{ inputs.repo }}-${{ inputs.pr }}`). No standalone eval workflow regression-tests `reviser` directly — `judge-evals.yml` and `failure-mode-evals.yml` cover `code-judge` and `founder-voice-pr-reviewer` only.

## Inputs

- Dispatch inputs: `pr`, `issue` (optional), `repo` (required), `round` (required — the failed judge round this revision answers)
- `/tmp/review-input/findings.md` — the judge's most recent `## code-judge:` comment on the PR
- `/tmp/review-input/reviews.md` — PR review bodies + inline review comments (`path:line` cited)
- `/tmp/review-input/diff.patch` — the PR's current diff against its base
- `/tmp/review-input/rounds.json` — prior rounds (`scripts/round-history.py read`)
- `/tmp/review-input/context.md` (PR title + body), `/tmp/review-input/ticket.json`, `/tmp/review-input/spec.md` (from `state/queue.json`'s `spec_path` for this `(issue, impl_repo)` claim) — whichever exist
- `./product` — the PR branch checked out, pushable origin (reviser does not push itself)
- `./guards/<repo>.paths` — expertise-guarded globs, off limits

## Outputs

- Commits on the PR branch in `./product` (not pushed by the reviser itself)
- `/tmp/review-output/changes.md` — Fixed / Not fixed, one entry per finding
- The workflow squashes the round into one bot-authored, attribution-stripped commit (`./.github/actions/strip-attribution`) and pushes with `--force-with-lease`
- A round comment on the PR, the round recorded in the PR body's round block, a `state/provenance.json` entry, and — on success — `code-judge.yml` re-dispatched for round+1

## Secrets and variables

`ANTHROPIC_API_KEY`, `BOT_APP_PRIVATE_KEY`, `BOT_APP_CLIENT_ID` (variable), `ANTHROPIC_WORKSPACE_ID` (variable, via `ANTHROPIC_CUSTOM_HEADERS`), `SLACK_BOT_TOKEN`. Gated on `vars.AGENT_OPS_PAUSED != 'true'`.

## Run it by hand

```bash
gh workflow run revise.yml -f pr=<n> -f repo=<impl-repo> -f round=<n> [-f issue=<n>]
```
`round` must be the failed judge round being answered (it errors if `round >= ROUND_CAP` — code-judge should already have handed that PR to a human). There is no dry-run/cases-subset flag; `reviser` is not exercised by any eval harness.

## Pause / kill switch

`AGENT_OPS_PAUSED=true` skips the whole job. `reviser` is the other half of CLAUDE.md hard rule 8's round-cap/cost-ceiling loop: `ROUND_CAP=3`, cost ceiling `COST_CEILING_USD` per ticket, tracked in the PR body via `scripts/round-history.py`. A reviser run that finds nothing fixable in scope (`RESULT: BLOCKED`), or any workflow failure here, labels the PR `agent:needs-human` — every exit lands on a human, per rule 8.

## How it fails and where the alert goes

`RESULT: BLOCKED` (or `REVISED` with no commit, treated as blocked) is a legitimate terminal state, not a workflow failure: it labels the PR `agent:needs-human` and posts `:raised_hand: Revise round $ROUND could not fix the judge's findings in scope on ... — ${REASON}` plus the round history to `${SLACK_OPS_CHANNEL_ID}` (`scripts/slack-alert.sh`). A genuine workflow failure (crash, expertise-guard or footprint-scan rejection, push failure) also labels `agent:needs-human` and posts `:x: revise round $ROUND failed on ... — labeled agent:needs-human, nothing was pushed unless the log says so` to `${SLACK_OPS_CHANNEL_ID}`, suppressed if `scripts/is-systemic-failure.sh` flags it as infra-wide. Unlike `code-judge`, a reviser failure does keep the PR from advancing — no re-judge is dispatched.

## Files this node touches

`agents/reviser/CLAUDE.md`, `.github/workflows/revise.yml`, `.github/workflows/code-judge.yml` (dispatcher + next-round target), `scripts/round-history.py`, `scripts/result-line.sh`, `scripts/expertise-path-guard.sh`, `scripts/footprint-scan.sh`, `scripts/record-provenance.sh`, `scripts/slack-alert.sh`, `.github/actions/strip-attribution`, `guards/<repo>.paths`, `state/queue.json` (spec_path lookup), `state/provenance.json`.

## Owner

See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
