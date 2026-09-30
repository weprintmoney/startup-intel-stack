# release-intelligence-miner

## Purpose

Scores every merged PR in a `example-app-core` release window against the target-ICP rubric (not the existing customer base — founder-relationship pull is a trailing indicator and must not dominate scores). First stage of the release-intelligence pipeline: it produces findings, it never opens tickets or posts to Slack itself.

## Trigger and cadence

No standalone trigger — it's a step ("Run release-intelligence-miner") inside job `release-intelligence` in `.github/workflows/release-intelligence.yml`. That workflow fires on cron `45 */6 * * *`, on `repository_dispatch: release-published` from an optional caller in `example-app-core`, and on `workflow_dispatch` (`tag`, `lookback_days` inputs). The miner step only runs when the "Prepare miner input" step finds at least one merged PR in the detected release window (`steps.prep.outputs.mine == 'true'`).

## Inputs

All staged under `/tmp/mine-input/` by the "Prepare miner input" step: `rubric.md` (internal-docs `07-engineering-docs/release-intelligence/rubric.md`, authoritative 5-dimension 0–2 scoring), `run-meta.json` (`release_tag`, `repo`, `run_url`, `rubric_version`, `market_worthy_min`), `icp.mdx` (internal-docs ideal-customer-profile), `positioning-claims.json` (graph nodes where `graph_type == "positioning-claim"`), `market-signals.md` (latest 2 `01-market-intelligence/analyst-signals/*.md` files — capped at `market_resonance <= 1` if the newest is older than 14 days), `prs.json` (merged PRs in the release window, `number`/`title`/`url`/`body`). May also call read-only `gh api` for a PR's diff/files when title+body aren't enough.

## Outputs

`/tmp/mine-output/release-findings.json` conforming to `schemas/release-findings.schema.json`: one `findings[]` entry per PR with per-dimension scores, `total`, `verdict`. Ends with exactly one `RESULT: FINDINGS <n> MARKET_WORTHY <n>` (or `RESULT: ERROR <reason>`) line. That file is committed to `state/releases/<tag>/findings.json` by a later deterministic step.

## Secrets and variables

`ANTHROPIC_API_KEY`, variable `ANTHROPIC_WORKSPACE_ID` (custom header), `GH_TOKEN` = the minted `example-app-bot` product-repo token (read-only). The surrounding job is gated on `BOT_APP_PRIVATE_KEY` + `BOT_APP_CLIENT_ID` (App mint) and `ANTHROPIC_API_KEY` all being set ("Gate on secrets" step); `SLACK_BOT_TOKEN` is used by later steps in the same job, not by the miner step itself.

## Run it by hand

```bash
gh workflow run release-intelligence.yml -f tag=<release-tag> -f lookback_days=<n>
```
`tag` defaults to the latest unprocessed non-prerelease; `lookback_days` overrides the PR window start (default: previous release's publish date).

## Pause / kill switch

`if: vars.AGENT_OPS_PAUSED != 'true'` on the `release-intelligence` job — set the repo variable to skip the whole run, miner included. The job also short-circuits (no-op) if the App secrets/`ANTHROPIC_API_KEY` are missing, or if the detected release was already processed (`state/releases/<tag>/findings.json` exists and no explicit `tag` input was given).

## How it fails and where the alert goes

Model arithmetic is never trusted: a later "Validate findings (schema + arithmetic, deterministic)" step re-checks schema conformance, `total == sum(scores)`, verdict/threshold consistency, and evidence-required-on-market-worthy via `scripts/validate-release-findings.py`, independent of what the model claimed. If 0 PRs score market-worthy, `scripts/slack-alert.sh` (channel `${SLACK_OPS_CHANNEL_ID}`) posts a "0 of N merged PRs market-worthy" notice. Any hard failure in the job (miner included) is caught by the job's `Alert on failure` step, which posts `release-intelligence failed for <tag>` to the same channel — the run is abandoned, not retried.

## Files this node touches

`agents/release-intelligence-miner/CLAUDE.md`, `.github/workflows/release-intelligence.yml`, `schemas/release-findings.schema.json`, `scripts/validate-release-findings.py`, `scripts/run-claude.sh`, `scripts/log-token-usage.sh`, `scripts/slack-alert.sh`, `scripts/commit-state.sh`, `state/releases/<tag>/findings.json`, and (read-only) internal-docs `07-engineering-docs/release-intelligence/rubric.md`, `01-market-intelligence/ideal-customer-profile.mdx`, `01-market-intelligence/analyst-signals/`, `.claude/indexes/graph.json`.

## Owner

See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
