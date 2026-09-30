# dream-orchestrator

## Purpose

Weekly self-improvement loop for the agent-ops pipeline: mines its own exhaust — session transcripts, human corrections on agent PRs, judge-vs-human disagreements, doc drift — for patterns that recur 3 or more times, then proposes durable memory updates so the same correction never has to be made twice. A synthesizer, not an enforcer: every output lands as a PR a human must approve.

## Trigger and cadence

Cron `0 8 * * 0` (Sundays 3 AM ET) plus `workflow_dispatch` (`lookback_days` input, default `9`), both in `.github/workflows/dream.yml`, job `dream`. The orchestrator runs twice in that one job, selected by the `DREAM_STAGE` env var: `mine` (step "Run dream orchestrator (mine)") and, after a separate `miner-verify` gate node runs between them, `draft` (step "Run dream orchestrator (draft)"). Stage `all` exists for local dry-runs only — CI never uses it.

## Inputs

- `sessions/YYYY-WW/*.stream.jsonl` transcripts, `evals/pr-cases/` fixtures, `schemas/miner-findings.schema.json`, `guards/*.paths` (product-repo list)
- `./internal-docs/` — writable checkout of `internal-docs`: graph `.claude/indexes/graph.json`, `.claude/team-memory/`, `.claude/rules/`, staleness digest at internal-docs issue #422
- Stage `draft` reads validated findings the workflow already wrote to `/tmp/dream/findings/` (miners quarantined by the verify gate are absent from that directory)
- Spawns 3 Task-tool subagents in stages `mine`/`all`, one per prompt file under `agents/dream-orchestrator/miners/`: `transcript-failure-miner.md` (dead-ends, wrong assumptions, missing context in pipeline transcripts), `review-delta-miner.md` (human review comments, post-bot commits, judge-vs-human disagreements on agent PRs), `doc-drift-miner.md` (graph nodes contradicted by merged code, staleness re-verification)

## Outputs

- Stage `mine`: `/tmp/dream/findings/<miner>.json` + `/tmp/dream/summaries/<miner>.md` per healthy miner
- Stage `draft`: at most one memory PR to `internal-docs` (`.claude/team-memory/`, graph frontmatter, `.claude/rules/`, regenerated `.claude/indexes/graph.json`) titled `dream: memory updates <YYYY-WW>`; optionally a fixture PR to this repo's `evals/pr-cases/` (branch `dream/fixtures-<YYYY-WW>`); rarely, self-improvement PRs to `agents/*/CLAUDE.md` (branch `dream/prompts-<YYYY-WW>`) or internal-docs rubric/skills (branch `dream/rubric-<YYYY-WW>`)

## Secrets and variables

`ANTHROPIC_API_KEY`, `BOT_APP_PRIVATE_KEY` + `BOT_APP_CLIENT_ID` (mint the internal-docs write token and the product-repo read token), `SLACK_BOT_TOKEN`. Variables `ANTHROPIC_WORKSPACE_ID` (custom header) and `AGENT_OPS_PAUSED` (job gate). Missing any of the three secrets/vars checked in the "Gate on required secrets" step degrades the whole job to a no-op.

## Run it by hand

```bash
gh workflow run dream.yml -f lookback_days=<n>
```

## Pause / kill switch

`if: vars.AGENT_OPS_PAUSED != 'true'` on the `dream` job — set the repo variable to skip the entire run. No node-specific override; the job also self-degrades to a no-op if `ANTHROPIC_API_KEY`, `BOT_APP_PRIVATE_KEY`, or `BOT_APP_CLIENT_ID` is unset.

## How it fails and where the alert goes

Every completed run posts to Slack via `scripts/slack-alert.sh` (channel `${SLACK_OPS_CHANNEL_ID}`): `PROPOSED` (with the memory/fixture/improvement PR links), `NO_SIGNAL` (no cluster cleared the 3x evidence bar), or a warning if no `RESULT:` line was emitted. If the miner-verify gate quarantines any miner's findings over an unsupported claim, that message is prefixed with the quarantined miners and up to 10 unsupported claims, and no memory PR opens that run. A hard job failure goes through a separate `Alert on failure` step — suppressed if `scripts/is-systemic-failure.sh` flags it as systemic, otherwise posted as a run failure with no automatic retry.

## Files this node touches

`agents/dream-orchestrator/CLAUDE.md`, `agents/dream-orchestrator/miners/{transcript-failure-miner,review-delta-miner,doc-drift-miner}.md`, `.github/workflows/dream.yml`, `agents/miner-verifier/CLAUDE.md` (the verify-stage node's prompt), `schemas/miner-findings.schema.json`, `scripts/run-claude.sh`, `scripts/result-line.sh`, `scripts/log-token-usage.sh`, `scripts/slack-alert.sh`, `scripts/is-systemic-failure.sh`, `state/dream/<run_id>/quarantine/`, `sessions/<week>/`.

## Owner

See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
