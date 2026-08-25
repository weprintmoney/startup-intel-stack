# Setup — human-action items

These require org-admin or account-level actions Claude cannot perform.
Check off as completed. Everything below maps to the L3-0 "Plumbing and
safety floor" gate in
[`../../docs/00-foundations/the-coding-harness.md`](../../docs/00-foundations/the-coding-harness.md).

## 1. Bot account

- [ ] Create a GitHub account with a neutral name (no "Claude", "AI", or
      model reference). Example: `example-app-eng-bot`. Use a role-address
      email you control (`eng@` or `bot@` on your domain)
- [ ] Invite it to `<YOUR_ORG>` as a member
- [ ] Grant write on product repos (`<YOUR_ORG>/example-app-core`,
      `<YOUR_ORG>/example-app-service`, SDK repos) and on `<YOUR_ORG>/agent-ops`
- [ ] Grant contents+PR write on `<YOUR_ORG>/internal-docs` (dream loop
      target)

## 2. PAT matrix (least privilege — one token per capability)

Create each as a fine-grained personal access token owned by the bot
account, then add to this repo's secrets under the name below.

| Secret name | Scope | Used by |
|---|---|---|
| `INTERNAL_DOCS_RO_PAT` | `<YOUR_ORG>/internal-docs`, contents **read** | All task agents (`spec-drafter`, `implementer`, `pr-reviewer`, `founder-voice-pr-reviewer`, `code-judge`) |
| `INTERNAL_DOCS_PR_PAT` | `<YOUR_ORG>/internal-docs`, contents + pull-requests **write** | Dream loop ONLY |
| `PRODUCT_REPOS_PAT` | Product repos, contents + pull-requests **write** | `implement.yml` PR-open step, `code-judge.yml` commit-status write |
| `SALES_OPS_RO_PAT` | `<YOUR_ORG>/sales-ops`, contents **read** | Release-intelligence prospect-name guard only. Ticket drafting fails closed without this |
| `AGENT_OPS_READ_TOKEN` | `<YOUR_ORG>/agent-ops`, contents + actions **read** | Cost-digest, heartbeat, cross-workflow reads |

- [ ] All five PATs created and added as repo secrets

## 3. Anthropic + Slack secrets

- [ ] `ANTHROPIC_API_KEY` — dedicated key for this pipeline (separate from
      other loops so `cost-digest` can attribute spend cleanly)
- [ ] `ANTHROPIC_ADMIN_KEY` — Admin API key for the org cost-report
      endpoint (Anthropic Console → Settings → Admin keys)
- [ ] `SLACK_BOT_TOKEN` — bot must be invited to the ops channel
      (`${SLACK_OPS_CHANNEL_ID}`) before any workflow can post

## 4. Cost ceiling (Guardrail 1)

Wire this **before** anything else runs. A runaway agent that discovers
your API key has no ceiling is the single most expensive failure mode in
the whole system.

- [ ] Decide a weekly dollar ceiling (start conservative — `$150` is a
      reasonable first value)
- [ ] Set repo variable `WEEKLY_COST_CEILING_USD` to that number
- [ ] Set repo variable `AGENT_OPS_PAUSED=false`
- [ ] Record the ceiling in your `internal-docs/terminus/operational-guardrails.md`

Behavior once set: `cost-digest.yml` posts weekly spend to Slack. ≥70% of
ceiling → warning. ≥100% → sets `AGENT_OPS_PAUSED=true` (global hard-stop
for non-exempt workflows) plus a critical alert. Only a human clears it.

## 5. Slack channels

- [ ] Create a dedicated ops channel; capture its ID as
      `SLACK_OPS_CHANNEL_ID` (see `.env.example`)
- [ ] Invite the Slack bot to that channel
- [ ] Optional: `SLACK_EXEC_CHANNEL_ID` for the exec-only channel —
      pipeline never posts here, but the identity is checked so nothing
      accidentally does

## 6. Later phases (not blocking L3-0)

- [ ] Product repos: add `expertise-path-guard` + `footprint-scan` as
      **required checks** on `agent/*` branches (L3-2 gate)
- [ ] Ensure `agent:queued`, `mode:claude-led`, `class:*`, and
      `agent:proposed` labels exist on the sprint board (L3-2 / L3-4)
- [ ] Populate `guards/prospect-names.txt` in `<YOUR_ORG>/sales-ops`
      with target-prospect names — one per line, `#` comments allowed.
      An empty list means the guard passes trivially. Missing file =
      no tickets open, fail closed (L3-4)
- [ ] `PRODUCT_REPOS_PAT` additionally needs **organization project**
      scope so proposed tickets land on your sprint project (degrades to
      label-only with a warning otherwise) (L3-4)
- [ ] Optional: thin caller workflow in your product repo sending
      `repository_dispatch` type `release-published` (payload
      `{"tag": "<tag>"}`) to `<YOUR_ORG>/agent-ops` for instant release
      processing — the 6h cron poll covers it otherwise (L3-4)

## 7. First run

- [ ] Confirm `pipeline-heartbeat.yml` runs green on schedule and posts to
      Slack
- [ ] Confirm `schema-validate.yml` runs green on every push
- [ ] Confirm `cost-digest.yml` posts weekly spend to Slack
- [ ] Label one throwaway ticket `agent:queued` + `mode:claude-led` +
      `class:docs-scaffolding` and confirm `ticket-intake.yml` claims it
- [ ] Manually dispatch `spec-draft.yml`; approve the spec PR
- [ ] Manually dispatch `implement.yml`; confirm the two review transcripts
      land on the resulting PR
- [ ] Only then flip on `code-judge.yml` as advisory, then as required
