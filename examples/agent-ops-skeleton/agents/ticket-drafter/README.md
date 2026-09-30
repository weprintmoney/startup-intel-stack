# ticket-drafter

## Purpose

Turns market-worthy release-intelligence findings into proposed backlog tickets — one Problem / What to create / Acceptance-criteria issue per finding. It never opens issues itself: a deterministic workflow step opens them from its output files after a prospect-name scan. Tickets land with `agent:proposed` only; a human must swap the label to `agent:queued` before anything enters the coding pipeline.

## Trigger and cadence

A step ("Run ticket-drafter") inside job `release-intelligence` in `.github/workflows/release-intelligence.yml` (same workflow/cron/dispatch as `release-intelligence-miner`). **Currently held**: the preceding "Gate ticket drafting (held pending sales-ops access decision)" step hardcodes `go=false` before doing anything else, so the drafter step (`if: steps.ticketgate.outputs.go == 'true'`) does not run in production regardless of how many findings score market-worthy — see SETUP.md §3.

## Inputs

`/tmp/draft-input/findings.json` — market-worthy findings only, with PRs excluded by claim-verify already filtered out (`select(.verdict == "market-worthy" and (.pr_number not in contradicted_prs))`), conforming to `schemas/release-findings.schema.json` finding entries — plus `/tmp/draft-input/run-meta.json` (`release_tag`, `repo`, `run_url`).

## Outputs

One `/tmp/draft-output/ticket-<pr_number>.md` per finding, in the fixed `TITLE:` / Problem / What to create / Acceptance-criteria shape its `CLAUDE.md` specifies — no other sections. Ends with exactly one `RESULT: TICKETS <n> SKIPPED <n>` (or `RESULT: ERROR <reason>`) line. Downstream, the "Scan and open proposed tickets" step turns surviving files into GitHub issues on `example-app-core`, labeled `agent:proposed` + `release-intelligence`, added to Project #4.

## Secrets and variables

The drafter step itself only needs `ANTHROPIC_API_KEY` and variable `ANTHROPIC_WORKSPACE_ID` (custom header) — it has no `Bash` tool and never calls `gh`. The job around it is gated on `BOT_APP_PRIVATE_KEY` + `BOT_APP_CLIENT_ID` and `ANTHROPIC_API_KEY`. Its **prospect-name guard** (`scripts/prospect-name-scan.sh`) is designed to fail closed against a blocklist fetched at run time from `<YOUR_ORG>/sales-ops` (`guards/prospect-names.txt`) via a `SALES_OPS_RO_PAT` secret — but per SETUP.md §3 that mint/fetch step is currently commented out in this workflow, which is the reason ticket drafting is held rather than the guard itself firing. `SLACK_BOT_TOKEN` is used by the gate/notify steps around the drafter, not the drafter step itself.

## Run it by hand

```bash
gh workflow run release-intelligence.yml -f tag=<release-tag>
```
This dispatches the whole release-intelligence workflow; the ticket-drafter step will still not run while the ticketgate step is hardcoded to `go=false` (see Trigger and cadence).

## Pause / kill switch

`if: vars.AGENT_OPS_PAUSED != 'true'` on the `release-intelligence` job applies same as for the miner. On top of that, the drafter has its own effective kill switch right now: the ticketgate step's hardcoded `go=false`, independent of `AGENT_OPS_PAUSED`.

## How it fails and where the alert goes

Every run where ≥1 finding is market-worthy posts to Slack (`scripts/slack-alert.sh`, channel `${SLACK_OPS_CHANNEL_ID}`) from the ticketgate step: the claim-verify summary (or a note that claim-verify didn't complete) plus "Ticket drafting held pending sales-ops access decision ... review manually and open tickets by hand if wanted." If the gate is ever re-enabled and issues open, the "Scan and open proposed tickets" step reports `BLOCKED` counts (drafts the prospect-name scan rejected) in the same Slack message. Any hard job failure is caught by the job's `Alert on failure` step, posted to the same channel — abandoned, not retried.

## Files this node touches

`agents/ticket-drafter/CLAUDE.md`, `.github/workflows/release-intelligence.yml`, `schemas/release-findings.schema.json`, `scripts/prospect-name-scan.sh`, `scripts/run-claude.sh`, `scripts/log-token-usage.sh`, `scripts/slack-alert.sh`, `scripts/commit-state.sh`, `state/releases/<tag>/proposed-tickets.json`.

## Owner

See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
