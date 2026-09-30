# Setup — human-action items

These require org-admin or account-level actions Claude cannot perform.
Check off as completed. Everything below maps to the L3-0 "Plumbing and
safety floor" gate in
[`../../docs/00-foundations/the-coding-harness.md`](../../docs/00-foundations/the-coding-harness.md).

Auth is a single **`example-app-bot` GitHub App**, not a bot user plus a matrix
of classic PATs. [`docs/github-app-setup.md`](docs/github-app-setup.md) has
the *why* — blast radius, escalation model, why Workflows-write is withheld —
and the worked token-mint example. This file is the checklist.

## 1. GitHub App — `example-app-bot`

- [ ] Create the App (org settings → Developer settings → GitHub Apps). Webhook off, "Only on this account"
- [ ] Permissions — repository: **Metadata: read** · **Contents: read+write** · **Pull requests: read+write** · **Issues: read+write** · **Commit statuses: read+write** · **Actions: read+write** · **Checks: read** (Dependabot triage reads check results) · **Workflows: no access** (deliberate — agents must not be able to edit CI). Organization: **Projects: read+write** only if claims move onto a project board
- [ ] Generate a private key (`.pem`) and note the Client ID
- [ ] Install on `<YOUR_ORG>/agent-ops`, your product repos (`example-app-core`, `example-app-service`, SDK repos) and `<YOUR_ORG>/internal-docs`. **Not** `sales-ops` (see §3)
- **Verifying an install:** run the `Install Preflight` workflow (`workflow_dispatch`, diagnostic only, not pause-gated). It mints an App JWT, checks `/repos/<YOUR_ORG>/<repo>/installation` for every repo in `state/impl-repos.json` plus anything passed in `extra_repos`, and fails with a per-repo table when a repo is uninstalled or installed with less than contents/PRs/issues write. Nothing about an install is visible to a user token, so this is the only way to confirm one without waiting for a pipeline run to 404.
- [ ] `spec-draft-orchestrator.yml` dispatches spec-draft with an App token scoped to `agent-ops` so each completion re-fires it via `workflow_run` (a `GITHUB_TOKEN` dispatch never does). That needs the App installed on `agent-ops` itself
- [ ] **Decide: Workflows: write.** Withheld on purpose. The cost: tickets that touch `.github/**` have to hand off to a human. Grant it and lean on the `.github/**` path guard, or keep it withheld and accept the hand-off
- [ ] Public product repos: `footprint-scan` must be a required check on `agent/*` in each before an agent PR can open (see §6)
- Repo variable **`DEPENDABOT_MODE`** — unset/anything = observe (classify + summary, zero PR writes); `act` = label / approve / merge per `state/dependabot-repos.json`. Leave unset until the first observe runs have been read

## 2. Repo variables and secrets (on `agent-ops` only, not org-wide)

| Name | Kind | Value |
|---|---|---|
| `BOT_APP_CLIENT_ID` | repo **variable** | Client ID from the App settings page (not secret) |
| `BOT_APP_PRIVATE_KEY` | repo **secret** | full `.pem` contents including `-----BEGIN`/`-----END` lines |

- [ ] Set `BOT_APP_CLIENT_ID` (variable) on this repo
- [ ] Set `BOT_APP_PRIVATE_KEY` (secret) on this repo
- [ ] Put the App's numeric bot ID into `.github/actions/bot-identity/action.yml` and the `strip-attribution` default (replace `<APP_ID>`; the runbook shows the one-line `gh api` lookup)

Keep these repo-scoped, not org-wide. An org secret is readable by every workflow that can see it, and any of those workflows could mint a token with the *full* installation permissions across every installed repo. If a second repo ever needs the App, use org-secret **"Selected repositories"** visibility (never "All repositories"). Later, promote `BOT_APP_PRIVATE_KEY` to a **GitHub Environment** secret with protection rules.

## 3. `sales-ops` access — decide the mechanism

`release-intelligence.yml` needs read access to `<YOUR_ORG>/sales-ops/guards/prospect-names.txt` for the prospect-name guard on proposed tickets. Two workable mechanisms, both fail closed: a fine-grained read-only PAT, or installing the App on `sales-ops` with a mint-time read-only scope-down. The tradeoff is "one more PAT to rotate" versus "App installed on a confidentiality-sensitive repo" — a call for whoever owns that confidentiality.

Until decided, ticket drafting stays commented out in `release-intelligence.yml`: the workflow still scores every stable release against the target-ICP rubric and writes findings to `state/releases/<tag>/findings.json`, and Slack tells you when something is market-worthy so you can file tickets by hand.

- [ ] Decide the mechanism (PAT vs App-install) and wire it (uncomment the mint block in `release-intelligence.yml`)
- [ ] Populate `guards/prospect-names.txt` in `<YOUR_ORG>/sales-ops` with target-prospect names — one per line, `#` comments allowed. An empty list passes trivially; a missing file means no tickets open (fail closed)

Worth asking whether the guard should exist at all: its presence means agent-ops has transient read across the confidentiality boundary. The alternative is to constrain the ticket-drafter's output template so it structurally cannot contain free-form customer names.

## 4. Anthropic, Slack, and the cost ceiling

- [ ] `ANTHROPIC_API_KEY` — dedicated key for this pipeline, running under its own Anthropic workspace so rate limits and budgets are isolated from interactive use and `cost-digest` can attribute spend cleanly. If the key's scope covers the org `cost_report` endpoint, no separate admin key is needed
- [ ] `ANTHROPIC_ADMIN_KEY` *(optional)* — a dedicated Admin API key. If set, `cost-digest` / `metrics-digest` / `budget-guard` prefer it over `ANTHROPIC_API_KEY` for the cost-report call
- [ ] Repo variable `ANTHROPIC_WORKSPACE_ID` — the pipeline's workspace. Spend checks are scoped to it; without it the digests refuse to report the org-wide number as pipeline spend
- [ ] `SLACK_BOT_TOKEN` — bot must be invited to the ops channel
- [ ] Repo variable `SLACK_OPS_CHANNEL_ID` — the ops channel's ID (see `.env.example`). Workflows pass it to `scripts/slack-alert.sh`; without it alerts are logged only
- [ ] Optional: `SLACK_EXEC_CHANNEL_ID` for the exec-only channel — the pipeline never posts here, but the identity is checked so nothing accidentally does

### Cost ceiling (Guardrail 1)

Wire this **before** anything else runs. A runaway agent that discovers your API key has no ceiling is the single most expensive failure mode in the whole system.

- [ ] Decide a weekly dollar ceiling. It is a safety rail, not a budget: size it so a pilot cannot halt after a few tickets just to teach you the ceiling works (a pilot ticket running plan + implement + two reviews + judge plausibly costs tens of dollars)
- [ ] Set repo variable `WEEKLY_COST_CEILING_USD` to that number
- [ ] Set repo variable `AGENT_OPS_PAUSED=false` (`true` stops every pause-gated workflow)
- [ ] Record the ceiling in your `internal-docs/terminus/operational-guardrails.md`

Behavior: `cost-digest.yml` posts the pipeline-workspace slice of weekly spend to Slack (org-wide total alongside it, as unchecked context); ≥70% of ceiling → warning; ≥100% → loud alert. **Separately, `budget-guard.yml` checks the same spend every 15 minutes and sets `AGENT_OPS_PAUSED=true` the moment the ceiling is hit**, so a burst is caught in minutes, not at the next digest.

Why `cost-digest` itself pauses nothing: writing an Actions variable needs an admin/App credential. The default `GITHUB_TOKEN` gets a 403 no matter what `actions: write` says.

- [ ] **Grant the App "Variables: Read and write"** (distinct from "Actions") on `agent-ops` — App settings → Permissions → Repository → Variables, then approve the re-installation prompt. Until granted, `budget-guard.yml` degrades to a "set it manually" Slack alert and activates automatically the moment the permission lands

### Eval-suite cost controls

Eval suites (Opus, dozens of cases) that rerun on every push to a PR iterating on the judge/eval framework itself are the classic way to burn a week's budget in a day. Two mechanical fixes ship in the workflows: concurrency cancellation on all eval suites (a new push cancels the still-running prior full eval) and a draft-PR skip (the expensive model loop skips entirely while the PR is a draft).

Policy, not just mechanism: when iterating on judge/eval/rubric prompts, open the PR as a **draft** and do the tight loop locally in your own Claude Code session (`evals/run_eval.py`, billed to your seat, not this pipeline's key). Mark the PR ready only once you believe it is correct. CI is the pre-merge gate, not the iteration loop.

## 5. Claude Code version pin

- [ ] Set `.claude-code-version` to a CLI release you have smoke-tested. Every workflow installs exactly that version (`.github/actions/setup-claude`), because the stream-json fields the pipeline parses are an unversioned contract. **Switching models is one PR that bumps this pin and smoke-tests a node on the new CLI** — the pin gates which models the pipeline can use.

## 6. Later phases (not blocking L3-0)

- [ ] Product repos: add `expertise-path-guard` + `footprint-scan` as **required checks** on `agent/*` branches (L3-2 gate). Both guards fetch their script from this private repo at run time, which a public caller's `GITHUB_TOKEN` cannot read; they accept an optional `AGENT_OPS_READ_TOKEN` and fail closed without it. A cleaner alternative is to reach the script through `uses: <YOUR_ORG>/agent-ops/.github/actions/...@main` (set the repo's Actions access policy to `organization`) and drop the token entirely
- [ ] Required-check wiring needs repo admin; if the bot or your team only has push on a repo, that is an admin action
- [ ] Ensure `agent:queued`, `mode:claude-led`, `class:*`, `repo:<name>`, `groom:review`, `groom:redo`, and `agent:proposed` labels exist on the sprint board (L3-2 / L3-4)
- [ ] Make `agent-ops/code-judge` a required status check on agent PRs (L3-3)
- [ ] The App additionally needs **organization Projects** scope if proposed tickets should land on your sprint project (degrades to label-only with a warning otherwise) (L3-4)
- [ ] Optional: thin caller workflow in your product repo sending `repository_dispatch` type `release-published` (payload `{"tag": "<tag>"}`) to `<YOUR_ORG>/agent-ops` for instant release processing — the 6h cron poll covers it otherwise (L3-4)
- [ ] Optional: repo variable `DEV_GUIDE_PATH` if your developer guide is not at the default path `docs-sync-check.yml` fetches
- [ ] Run [`docs/cold-start-exercise.md`](docs/cold-start-exercise.md) with a prospective second owner before you trust the docs

## 7. First run

- [ ] Run `Install Preflight`; confirm every expected repo reports installed
- [ ] Confirm `pipeline-heartbeat.yml` runs green on schedule and posts to Slack
- [ ] Confirm `schema-validate.yml` and `lint.yml` run green on every push
- [ ] Confirm `cost-digest.yml` posts weekly spend to Slack, and `budget-guard.yml` runs without error
- [ ] Label one throwaway ticket `agent:queued` + `mode:claude-led` + `class:docs-scaffolding` (+ `repo:<name>`) and confirm `ticket-intake.yml` claims it and the ticket gains one status card
- [ ] Watch `spec-draft-orchestrator.yml` dispatch `spec-draft.yml`; confirm the spec PR passes `claim-verify`; merge it (merging is the approval)
- [ ] Confirm `implement.yml` dispatches and the two review transcripts land on the resulting PR
- [ ] Only then flip on `code-judge.yml` as advisory, then as required; watch one full judge → revise → re-judge round before trusting the loop
- [ ] Bot commits render as **example-app-bot** with the App avatar. Grey/unlinked means the noreply email in `.github/actions/bot-identity` did not match
