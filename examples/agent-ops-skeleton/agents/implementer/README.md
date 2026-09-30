# implementer

## Purpose

Executes `plan.md`'s checklist on the claim branch, flipping each acceptance-criteria box in place as it's satisfied. Stage 3b of the coding loop — the branch is the checkpoint, so re-runs resume rather than restart, and it never opens the PR (fresh-context reviewers see the diff first).

## Trigger and cadence

No trigger of its own — it is the `implement` job inside `.github/workflows/implement.yml`, gated on `needs.plan.outputs.go == 'true'` (i.e. the `plan` job actually ran). Same `issue`/`branch`/`repo` inputs as the workflow dispatch that starts the whole pipeline. Its `respond.md` prompt is also invoked later, from the `open-pr` job's "Address or rebut findings" step, to address or rebut both fresh reviews before the PR opens.

## Inputs

- `./product/plan.md` — numbered steps, acceptance-criteria checklist, files-expected-to-change, Constraints (the spec's Non-goals, verbatim). Source of truth
- `./product/spec.md` — local copy of the spec, so it never re-fetches `internal-docs`
- `./product/` — the implementation repo, `BRANCH` checked out (any commits beyond the default branch are its own prior progress to continue, not restart)
- `./guards/<repo>.paths` — expertise-guarded globs it must never touch

## Outputs

- Commits on `BRANCH`, pushed to origin; `plan.md`'s `- [ ]` lines flipped to `- [x]` in place as each criterion is met
- `RESULT: IMPLEMENTED` or `RESULT: BLOCKED <reason>`
- If the bot App can't push a `.github/workflows/` file (Workflows:write withheld, decision #61), the "Hand off workflow files" step lifts it to `/tmp/handoff` and pushes the rest — the PR opens labeled `agent:needs-human` with the file attached instead of the run failing
- `/tmp/review-input/{diff.patch,spec.md,ticket.json|intent-note.md}` packaged for the two review jobs, and later (via `respond.md`) `/tmp/review-output/responses.md`

## Secrets and variables

`ANTHROPIC_API_KEY`, `BOT_APP_PRIVATE_KEY` + repo variable `BOT_APP_CLIENT_ID` (mint three separate short-lived tokens in this job: checkout, hand-off push, and review-input packaging), repo variable `ANTHROPIC_WORKSPACE_ID`. No `SLACK_BOT_TOKEN` in this job directly.

## Run it by hand

Not dispatchable standalone — it is the `implement` job inside `implement.yml`, not its own workflow:
```bash
gh workflow run implement.yml -f issue=<n> -f branch=agent/<n>-<slug> -f repo=<impl-repo>
```
Because the branch is the checkpoint, re-dispatching resumes from whatever is already committed past the default branch rather than starting over.

## Pause / kill switch

No `AGENT_OPS_PAUSED` check of its own — gated by `if: needs.plan.outputs.go == 'true'`, which is false whenever the `plan` job was paused or soft-no-op'd on missing secrets. Pausing upstream skips this job transitively.

## How it fails and where the alert goes

Two specific "failures" are deliberately not failures: a `github-app-missing-workflows-permission` BLOCKED result is turned into a `::warning::` and `exit 0` by "Gate on implementer result" (continues as a human hand-off), and unchecked acceptance-criteria lines are only a warning when a handoff is in play. Any other BLOCKED result, or unchecked criteria with no handoff, fails the job. The shared `alert-on-failure` job (`needs: [plan, implement, review-generic, review-founder-voice, open-pr]`, `if: failure() && needs.plan.outputs.go == 'true'`) checks whether the implementer step ever ran (`needs.implement.outputs.result`). If it never got that far — failed at claim-marking, checkout, or branch-resume — nothing was attempted this run, so the claim is left as-is and only Slack hears about it (`:warning:`). Otherwise it abandons the claim, comments on the issue, and alerts Slack `${SLACK_OPS_CHANNEL_ID}` via `scripts/slack-alert.sh`: `:x: implement pipeline failed for $TICKET_REPO#$ISSUE ($IMPL_REPO) — claim abandoned, branch $BRANCH kept. $RUN_URL`.

## Files this node touches

`agents/implementer/CLAUDE.md`, `agents/implementer/respond.md` (the later respond pass in `open-pr`), `.github/workflows/implement.yml` (`implement` and `open-pr` jobs), `.github/actions/bot-identity`, `.github/actions/setup-claude`, `.github/actions/strip-attribution` (scrubs its commits before push), `scripts/run-claude.sh`, `scripts/result-line.sh`, `scripts/log-token-usage.sh`, `scripts/update-claim.sh`, `scripts/expertise-path-guard.sh`, `scripts/footprint-scan.sh`, `guards/<repo>.paths`.

## Owner
See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
