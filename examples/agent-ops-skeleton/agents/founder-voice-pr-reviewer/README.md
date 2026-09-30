# founder-voice-pr-reviewer

## Purpose

Fresh-context reviewer that judges the implementer's diff in <FOUNDER_NAME>'s voice, on Opus, against the domain checklist for your product's differentiating concerns. The other of the two parallel fresh-context reviews before a PR opens — the generic-model counterpart is `pr-reviewer`.

## Trigger and cadence

No trigger of its own — it is the `review-founder-voice` job inside `.github/workflows/implement.yml`, gated on `needs.implement.outputs.go == 'true'` and running in parallel with `review-generic` once the `implement` job succeeds. Same `issue`/`branch`/`repo` inputs as whatever dispatched the workflow.

## Inputs

- `/tmp/review-input/diff.patch` — downloaded from the `review-input` artifact the `implement` job uploaded
- Whichever of `spec.md`, `intent-note.md`, `context.md`, `ticket.json` are present in the same artifact
- `./internal-docs/` — read-only checkout (fresh `bot-docs` token, `contents:read` scoped to `internal-docs` only)
- `state/failure-modes.json` — the enumerated failure-pattern catalog it cites inline by pattern ID; no `GH_TOKEN` is passed into the Claude run itself

## Outputs

- `/tmp/review-output/review.md`: first line `VERDICT: approve|comment|request-changes`, then a founder-voice review — summary opening with light praise, inline `path:line` comments (with reference-section citations), a separate Domain risks section, and a `Review state` line (`APPROVED`/`COMMENTED`/`CHANGES_REQUESTED`) that must agree with the verdict
- Job output `verdict`; uploaded as artifact `review-founder-voice`, later attached verbatim into the PR body by `open-pr`

## Secrets and variables

`ANTHROPIC_API_KEY`, repo variable `ANTHROPIC_WORKSPACE_ID`; `BOT_APP_PRIVATE_KEY` + repo variable `BOT_APP_CLIENT_ID` (mint the internal-docs read-only token). No `SLACK_BOT_TOKEN`. Model is pinned in the workflow to `claude-opus-4-7` — the only Opus call in `implement.yml`; every other node runs `claude-sonnet-4-6`.

## Run it by hand

Not dispatchable standalone — it is the `review-founder-voice` job inside `implement.yml`, not its own workflow, and it always runs fresh (no skip/resume logic). Dispatch the whole pipeline:
```bash
gh workflow run implement.yml -f issue=<n> -f branch=agent/<n>-<slug> -f repo=<impl-repo>
```

## Pause / kill switch

No job-level `AGENT_OPS_PAUSED` check of its own — gated by `if: needs.implement.outputs.go == 'true'`, which just passes through `needs.plan.outputs.go`. Pausing (or a missing-secrets no-op) upstream on the `plan` job skips this job too.

## How it fails and where the alert goes

The job fails if the reviewer writes no `review.md`, or one with no recognizable `VERDICT: approve|comment|request-changes` first line. That feeds the shared `alert-on-failure` job (`needs: [plan, implement, review-generic, review-founder-voice, open-pr]`, `if: failure() && ...`): claim abandoned, issue comment, Slack `${SLACK_OPS_CHANNEL_ID}` alert (`:x: implement pipeline failed for $TICKET_REPO#$ISSUE ($IMPL_REPO) — claim abandoned, branch $BRANCH kept. $RUN_URL`). A clean `VERDICT: request-changes` is *not* a failure — `open-pr` labels the PR `agent:request-changes` and posts a separate Slack message to the same channel with both verdicts. This node has two additional drift nets, both alerting `${SLACK_OPS_CHANNEL_ID}`: `judge-evals.yml` (Mondays 7am ET, 27 historical PR cases, sets repo variable `AUTO_MERGE_FROZEN=true` on an unexplained flip) and `failure-mode-evals.yml` (Wednesdays 7am ET, synthetic failure-mode fixtures — alerts but does not freeze auto-merge, since those fixtures are expected to evolve).

## Files this node touches

`agents/founder-voice-pr-reviewer/CLAUDE.md`, `.github/workflows/implement.yml` (`review-founder-voice` job), `.github/workflows/judge-evals.yml`, `.github/workflows/failure-mode-evals.yml`, `state/failure-modes.json`, `evals/failure-mode-cases/**`, `evals/pr-cases/**`, `schemas/failure-mode-expected.schema.json`, `schemas/judge-verdict.schema.json`, `.github/actions/setup-claude`, `scripts/run-claude.sh`, `scripts/result-line.sh`, `scripts/log-token-usage.sh`.

## Owner
See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
