# claim-verifier

## Purpose

Fresh-context Sonnet invocation that checks a spec's or a release-finding's factual claims against canonical sources (feature catalog, invariants, behavior matrix, changelog, internal-docs graph, the product checkout) — never trusting the producing agent's prose. It is the claim-vs-canonical-source gate that runs after `spec-drafter` opens a spec PR and after `release-intelligence-miner` scores a release, resolving whatever a deterministic pre-pass could not.

## Trigger and cadence

`workflow_dispatch` only, no cron of its own. Invoked inline (same job) by:
- `spec-draft.yml`, job `spec`, step "Claim-verify the spec (fresh context)" — right after `spec-drafter` returns `RESULT: SPEC_PR` (`continue-on-error: true`, so a gate outage never fails the spec-draft run)
- `release-intelligence.yml`, job `release-intelligence`, step "Claim-verify market-worthy findings (fresh context)" — after findings validate and at least one is `market-worthy` (`continue-on-error: true`)

Re-runnable standalone via `claim-verify.yml` (job `verify`) for a spec PR that skipped the gate or was hand-corrected after a `contradicted` verdict. Regression-tested by `claim-verify-evals.yml` (`eval` job; PRs touching `agents/claim-verifier/**`, weekly Monday 11:00 UTC cron, dispatch) against the 5 fixtures in `evals/claim-verify-cases/` (3 clean + 2 planted); a separate `deterministic` job in the same workflow unit-tests `scripts/verify-claims.py` without a model.

## Inputs

Everything staged at `/tmp/claim-verify/` by the deterministic pre-pass (`scripts/verify-claims.py sources` then `extract`):

- `run-meta.json` — `artifact_kind` (`spec` | `release-findings`), `artifact_ref`, `run_url`
- `artifact.md` / `artifact.json` — the spec or release-findings text under audit
- `claims.json` — the pre-pass output (`verdict: pending` entries are the verifier's to resolve)
- `sources/` — `features.json`, `graph.json` + `internal_docs_dir`, `invariants.md`, `behavior-matrix.yaml`, `changelog.mdx` (from the `example-app-docs` public checkout), `retired-phrases.txt`, `manifest.json` (`product_dir`, `internal_docs_dir`)

`scripts/verify-claims.py` is the deterministic pre-pass — it decides everything a grep can decide (path citations that plainly don't exist, retired-phrase hits, etc.) before the model sees the `pending` remainder.

## Outputs

- `/tmp/claim-verify/verdict.json` — the verifier's own resolutions + enumerated claims
- `scripts/verify-claims.py aggregate` merges it with the pre-pass into `/tmp/claim-verify/final.json` + `final.md`
- On the spec/release PR: a verification block patched into the PR body (`patch-body`), and one of: nothing further (`verified`), label `claims:unverified`, or label `claims:contradicted` + the PR converted to draft + a PR comment + Slack
- On `release-intelligence.yml`: `state/releases/<tag>/claim-verdict.json`; findings with a `contradicted` claim are excluded from ticket drafting, `unverified` ones are footnoted on the ticket
- On `claim-verify.yml`: `claim_verification` recorded on the matching `state/queue.json` claim

## Secrets and variables

`ANTHROPIC_API_KEY`, `ANTHROPIC_WORKSPACE_ID` (variable, via `ANTHROPIC_CUSTOM_HEADERS`). The invoking workflows separately use `BOT_APP_PRIVATE_KEY` / `BOT_APP_CLIENT_ID` (variable) to mint the internal-docs and impl-repo read tokens, and `SLACK_BOT_TOKEN` for the contradicted/unverified/outage alerts. All three gate on `vars.AGENT_OPS_PAUSED != 'true'` at the job level (`spec-draft.yml`, `claim-verify.yml`, `release-intelligence.yml`).

## Run it by hand

The node itself is never dispatched alone — it has no standalone workflow entry point. To re-run the gate on an already-open spec PR:
```bash
gh workflow run claim-verify.yml -f pr=<internal-docs spec PR#> -f issue=<example-app-core ticket#> -f repo=<impl-repo>
```
To regression-test the prompt/pre-pass against the golden set (optionally a subset, or a proposed branch pre-merge):
```bash
gh workflow run claim-verify-evals.yml -f cases=<comma-separated case ids> -f verifier_ref=<branch>
```
There is no way to invoke `claim-verifier` on an arbitrary artifact outside `spec-draft.yml`, `claim-verify.yml`, `release-intelligence.yml`, or `claim-verify-evals.yml` — the pre-pass staging (`sources` + `extract`) is a prerequisite step baked into each of those.

## Pause / kill switch

`AGENT_OPS_PAUSED=true` skips the enclosing job in all three invoking workflows. The gate itself has no independent freeze switch, but `claim-verify-evals.yml`'s `freeze-on-drift` job sets `AUTO_MERGE_FROZEN=true` on a schedule/dispatch verdict flip (gate drift on main) — this blocks the Phase 5 auto-merge ladder repo-wide, not just claim-verify runs. A `verifier_ref`-scoped eval dispatch (proposed branch) blocks only that proposal, not `AUTO_MERGE_FROZEN`. `code-judge`'s round-cap/cost-ceiling loop (CLAUDE.md rule 8) is not applicable here — claim-verify is a one-shot gate, not part of that loop.

## How it fails and where the alert goes

In `spec-draft.yml` and `release-intelligence.yml`, the verify step is `continue-on-error: true`: a crash or timeout never fails the enclosing run. If the step produced no verdict/summary, the workflow posts `:warning: claim-verify errored on spec PR ... — the spec's claims were NOT checked` (spec) or reports "Claim-verify did NOT complete" in the release-scored Slack notice, both to `${SLACK_OPS_CHANNEL_ID}`. On a completed `contradicted` verdict: the spec/release PR is converted to draft, labeled `claims:contradicted`, commented, and `:no_entry_sign: claim-verify: spec PR ... has $N contradicted claim(s) — converted to draft, labeled claims:contradicted` is posted to `${SLACK_OPS_CHANNEL_ID}`. In standalone `claim-verify.yml`, a real job failure (not gated by continue-on-error) posts `:x: claim-verify failed for internal-docs PR #... — the spec's claims were NOT checked` to the same channel.

## Files this node touches

`agents/claim-verifier/CLAUDE.md`, `.github/workflows/spec-draft.yml`, `.github/workflows/claim-verify.yml`, `.github/workflows/claim-verify-evals.yml`, `.github/workflows/release-intelligence.yml`, `scripts/verify-claims.py` (+ `scripts/verify-claims_test.py`), `scripts/run-claim-verify-evals.py`, `scripts/slack-alert.sh`, `schemas/claim-verdict.schema.json`, `evals/claim-verify-cases/` (incl. `_fixtures/`), `state/queue.json`, `state/releases/<tag>/claim-verdict.json`.

## Owner

See [`06-operational/agent-ownership.md`](https://github.com/<YOUR_ORG>/internal-docs/blob/main/06-operational/agent-ownership.md) in `internal-docs`.
