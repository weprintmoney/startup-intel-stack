# miner-verifier

## Purpose

Fresh-context Sonnet invocation that checks a dream-loop miner's prose summary against its own `findings.json` and freshly-fetched evidence, catching "right actions, wrong report" (miscounted findings, fake or mismatched evidence links, unsupported verdict phrases) before a memory PR is drafted from it. It is the claim-vs-artifact gate between the dream loop's mine stage and its draft stage.

## Trigger and cadence

`workflow_dispatch` only, no cron of its own. Invoked inline by `dream.yml`, job `dream`, step "Miner verify (parallel, fresh context per miner)" — runs once per miner (`transcript-failure-miner`, `review-delta-miner`, `doc-drift-miner`) in parallel, each `--max-turns 20`, after the "mine" stage produces `findings.json` + `summary.md` for that miner and before the "draft" stage synthesizes the memory PR. `dream.yml` itself runs on a weekly schedule (Sundays 08:00 UTC / 3 AM ET) plus dispatch. Regression-tested by `verifier-evals.yml` (PRs touching `agents/miner-verifier/**`, weekly Monday 11:00 UTC cron, dispatch) against the 5 fixtures in `evals/miner-verify-cases/` (2 clean + 3 planted mismatches).

## Inputs

Everything staged at `/tmp/verify/<miner>/` by `dream.yml`'s verify step:

- `summary.md` — the miner's prose summary (the text under audit)
- `findings.json` — the miner's schema-validated artifact (ground truth for counts, entity names, evidence lists)
- `run-meta.json` — `miner` name, `run_url`, `lookback_days`

Evidence links cited in the summary are deliberately *not* passed in — the verifier fetches them itself (`gh api`, `gh pr view`, `gh issue view`, `curl`) rather than trusting the miner's claim that a link supports it.

## Outputs

- `/tmp/verify/<miner>.json` — `{miner, run_url, verified_at, verdict: supported|unsupported, claims: [...]}`, one entry per verifiable claim in the summary
- `dream.yml` aggregates all three verdicts: any `unsupported` quarantines that miner's `findings.json` into `state/dream/<run_id>/quarantine/` (committed to the repo) and excludes it from the draft stage
- No PRs, comments, or direct Slack messages come from the verifier itself — `dream.yml` folds the aggregated result into its own end-of-run Slack notice

## Secrets and variables

`ANTHROPIC_API_KEY`, `ANTHROPIC_WORKSPACE_ID` (variable, via `ANTHROPIC_CUSTOM_HEADERS`). The enclosing `dream.yml` job separately uses `BOT_APP_PRIVATE_KEY` / `BOT_APP_CLIENT_ID` (variable) to mint the internal-docs and product-repo tokens, and `SLACK_BOT_TOKEN` for the run's Slack notice. Gated on `vars.AGENT_OPS_PAUSED != 'true'` at the `dream` job level.

## Run it by hand

The node has no standalone dispatch — it only runs inside `dream.yml`'s per-miner loop, which cannot be targeted at one miner in isolation. To exercise it against the golden set (optionally a subset, or a proposed prompt branch pre-merge):
```bash
gh workflow run verifier-evals.yml -f cases=<comma-separated case ids> -f verifier_ref=<branch>
```
To run the real thing, dispatch the dream loop itself: `gh workflow run dream.yml -f lookback_days=<n>`.

## Pause / kill switch

`AGENT_OPS_PAUSED=true` skips the whole `dream` job (and with it, all three verifier invocations). There is no independent freeze switch for `miner-verifier` alone. `verifier-evals.yml`'s `freeze-on-drift` job sets `AUTO_MERGE_FROZEN=true` on a schedule/dispatch verdict flip (verifier drifted on main, not a proposed-branch eval) — this blocks the Phase 5 auto-merge ladder repo-wide. The round-cap/cost-ceiling loop in CLAUDE.md rule 8 (`code-judge` <-> `reviser`) does not apply here — the dream loop's own cost guard is the ≤30%-of-miner-cost budget enforced via `--max-turns 20` per verifier, not a round cap.

## How it fails and where the alert goes

Per-miner: if the verifier errors, `dream.yml` logs `::warning::verifier errored on $miner` and, having no verdict file to aggregate, quarantines that miner's findings conservatively (same effect as an `unsupported` verdict). Once aggregated across all three miners, `dream.yml`'s "Notify Slack" step posts to `${SLACK_OPS_CHANNEL_ID}`: if any miner was quarantined, `:rotating_light: *Dream verifier caught unsupported miner claims* — no memory PR this run. Quarantined miners: ...` followed by up to 10 unsupported-claim lines; if the whole `dream` job fails outright, `:x: Dream loop run failed — no memory PR this week. Not retrying ...` (suppressed if `scripts/is-systemic-failure.sh` flags it as infra-wide). A quarantine is not itself a workflow failure — the run still completes and reports `NO_SIGNAL` or `PROPOSED` depending on whether any miner survived.

## Files this node touches

`agents/miner-verifier/CLAUDE.md`, `.github/workflows/dream.yml`, `.github/workflows/verifier-evals.yml`, `scripts/run-verifier-evals.py`, `scripts/slack-alert.sh`, `scripts/is-systemic-failure.sh`, `schemas/miner-findings.schema.json`, `evals/miner-verify-cases/`, `state/dream/<run_id>/quarantine/`.

## Owner

See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
