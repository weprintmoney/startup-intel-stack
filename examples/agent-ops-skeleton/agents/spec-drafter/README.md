# spec-drafter

## Purpose

Turns a claimed sprint ticket into a 7-section implementation spec PR on `internal-docs` (or a one-paragraph fast-path intent note for docs-only / restoring-documented-behavior / contract-preserving changes). Stage 2 of the coding loop — writes specs, never product code.

## Trigger and cadence

`workflow_dispatch` only, fired by `spec-draft-orchestrator.yml` once per claimed ticket. Inputs: `issue` (product-repo issue number), `branch` (reserved `agent/<issue>-<slug>`), `repo` (implementation repo short name, default `example-app-core`). Runs on `claude-opus-5-5`. Concurrency is per claim (`group: spec-draft-<issue>-<repo>`): one run per claim, claims drafted in parallel, bounded only by `wip_cap`. Run title `Spec Draft #<issue> (<repo>)` is how the orchestrator matches in-flight runs to claims.

## Inputs

- The ticket (`gh issue view`, `TICKET_REPO=<YOUR_ORG>/example-app-core`), including comments
- `./product/` — read-only checkout of the implementation repo's default branch (ground-truth citations)
- `./internal-docs/` — writable checkout of `internal-docs` (graph, terminus docs, prior specs)
- `./guards/<repo>.paths` — expertise-guarded globs for the target repo
- `./agents/spec-drafter/named-people.yaml` — the only people the drafter may @-mention

## Outputs

- A spec PR on `internal-docs` at `07-engineering-docs/specs/features/<issue>-<slug>.md`, linted clean (`spec-lint.py`) before it opens — or, on the fast-path, an intent note posted on the product issue instead
- Human-facing ticket comments via the outbox (`/tmp/ticket-outbox/`, posted by the workflow through `scripts/status-card.py post-outbox`, which enforces the allowed kinds): one @-mention comment per named person with an open question, the clarifying question, or the blocker quote. Nothing else reaches the ticket from this node — the spec PR link, retries and abandons are rewrites of the ticket's single status card, and the drafter's own ticket token is read-only

## Secrets and variables

`ANTHROPIC_API_KEY`, `BOT_APP_PRIVATE_KEY` (mints the internal-docs push token, the drafter's read-only ticket token, and the workflow's ticket write token used for the outbox and the status card), `SLACK_BOT_TOKEN`. Repo variable `AGENT_OPS_PAUSED` gates the job (`if: vars.AGENT_OPS_PAUSED != 'true'`).

## Run it by hand

```bash
gh workflow run spec-draft.yml -f issue=<n> -f branch=agent/<n>-<slug> -f repo=<impl-repo>
```
Also how a `CLARIFY_NEEDED` claim resumes, once the ticket has an answer.

## Pause / kill switch

`AGENT_OPS_PAUSED=true` (repo variable) skips the job entirely. No node-specific override.

## How it fails and where the alert goes

Every exit — `SPEC_PR`, `FAST_PATH`, `GROOMING_BLOCKER`, `CLARIFY_NEEDED`, `DEPENDENCY_BLOCKED`, `UNFIT`, or a hard failure — posts to Slack via `scripts/slack-alert.sh` (channel `${SLACK_OPS_CHANNEL_ID}`). A hard failure retries up to 3 times (the count is on the ticket's status card), then abandons the claim; the `agent/<issue>-<slug>` branch survives as a checkpoint for re-dispatch. A claim-verify failure on the opened spec PR posts a separate alert and, on contradicted claims, converts the PR to draft and labels it `claims:contradicted` — the spec is NOT auto-fixed.

## Files this node touches

`agents/spec-drafter/CLAUDE.md`, `agents/spec-drafter/named-people.yaml`, `.github/workflows/spec-draft.yml`, `scripts/verify-claims.py` (claim-verify pre-pass), `scripts/status-card.py` (ticket status card + outbox), `scripts/slack-alert.sh`, `state/queue.json` (claim status), `schemas/queue-claim.schema.json`.

## Owner

See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
