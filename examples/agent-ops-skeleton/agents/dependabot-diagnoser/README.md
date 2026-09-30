# dependabot-diagnoser

## Purpose

The one model step inside Dependabot triage. A deterministic script has already classified a Dependabot PR and, for the "verification red here, green on main" case, decided `deps:blocked`. This node reads the failing job's log and writes a short, grounded "what broke and which bump most plausibly caused it" note so the human who picks it up starts from an answer instead of the log. It never gates the decision — that's already made before this node runs.

## Trigger and cadence

No trigger of its own — it is the model step inside `dependabot-triage.yml`'s job, which runs on a `schedule` (every 6h at :52) and `workflow_dispatch` (optional `repos`, `pr`, `mode` inputs). This node only runs for PRs the deterministic classifier (`scripts/dependabot-triage.py`) has already put in the regression case; most triage runs invoke it zero times.

## Inputs

Per case directory: `meta.json` (`repo`, `pr`, `check`, `workflow`, `head`), `bumps.json` (packages bumped: `name`, `from`, `to`, `class`), `log.txt` (tail of the failing job's log, ≤400 lines). Fresh context, no network, no shell — it sees only these three files.

## Outputs

`diagnosis.md` in the case directory: the failing symptom (quoted/paraphrased from the log), the most plausible responsible bump (or "no bump plausibly explains it"), an optional one-line fix, and a final `RESULT: DIAGNOSED` or `RESULT: INCONCLUSIVE` line. Posted as a comment on the Dependabot PR; carries no model attribution (may land on a public repo).

## Secrets and variables

`ANTHROPIC_API_KEY`, variable `ANTHROPIC_WORKSPACE_ID`. The surrounding job also needs `BOT_APP_PRIVATE_KEY` + `BOT_APP_CLIENT_ID` (App token mint) and `SLACK_BOT_TOKEN` (failure alert only — this node's own output never goes to Slack).

## Run it by hand

Not dispatchable standalone — it's a step inside `dependabot-triage.yml`, invoked only when the classifier hits the regression case for a given PR. Dispatch the whole workflow scoped to one PR:
```bash
gh workflow run dependabot-triage.yml -f repos=<repo> -f pr=<n> -f mode=observe
```
`mode=observe` (or leaving `DEPENDABOT_MODE` unset) never writes to the PR — classify + step summary only.

## Pause / kill switch

`AGENT_OPS_PAUSED=true` skips the whole job. Separately, `DEPENDABOT_MODE` gates all PR-writing behavior repo-wide: anything but the literal `act` (repo variable) means observe-only — this node may still run and write `diagnosis.md`, but nothing gets posted to the PR. Per-repo: a repo absent from `state/dependabot-repos.json` is never touched at all.

## How it fails and where the alert goes

This node itself has no failure path that alerts Slack — an errored or timed-out diagnosis is logged inline (`echo "::warning::dependabot-diagnoser errored for $REPO#$NUM — labeled without a diagnosis"`) and the PR is still labeled `deps:blocked`, just without the comment. The one Slack alert in this workflow is job-level: `scripts/slack-alert.sh` posts `:x: dependabot-triage failed — Dependabot PRs are unattended until the next run (6h)` to `${SLACK_OPS_CHANNEL_ID}` on a hard job failure.

## Files this node touches

`agents/dependabot-diagnoser/CLAUDE.md`, `.github/workflows/dependabot-triage.yml`, `scripts/dependabot-triage.py`, `scripts/run-claude.sh`, `scripts/slack-alert.sh`, `state/dependabot-repos.json`, `evals/dependabot-cases/`, `sessions/YYYY-WW/dependabot-diagnoser-*` (secret-scrubbed transcripts).

## Owner

See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
