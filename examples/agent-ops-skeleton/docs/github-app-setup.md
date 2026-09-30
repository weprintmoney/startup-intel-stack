# GitHub App setup runbook

Replaces the classic PAT matrix in [`../SETUP.md`](../SETUP.md) §2 with a single GitHub App (`example-app-bot`). Use this if you would rather not create a bot user and hand out long-lived tokens; the workflows in this skeleton mint short-lived App installation tokens (`BOT_APP_CLIENT_ID` / `BOT_APP_PRIVATE_KEY`).

## Why an App instead of PATs

| | Classic PAT | GitHub App |
|---|---|---|
| Lifetime | Long-lived, manual rotation | Installation tokens expire in 1 hour |
| Scope | Carries the **user's** whole access | Per-repo, per-permission |
| Identity | Indistinguishable from a human | Auditable separately as `example-app-bot[bot]` |
| Blast radius | One leak exposes every repo the user can reach | Bounded to the installation |

One conceptual note, because it trips people up: **installing the App is the authorization** (what it may do, on which repos). **The private key is the identity** (proof that a workflow *is* the App). A workflow needs both — it signs a JWT with the key, exchanges that for an installation token, and uses the token for git and API work. That is why a secret is still required even though the App is installed.

---

## 1. Create the App

Org settings → Developer settings → GitHub Apps → New GitHub App.

- Name: `example-app-bot`
- Homepage URL: `https://github.com/<YOUR_ORG>/agent-ops`
- Webhook: **Active unchecked** — the pipeline is cron/dispatch driven, and leaving it on just generates delivery failures to ignore
- Where can this be installed: Only on this account

## 2. Permissions

**Repository permissions**

| Permission | Level | Why |
|---|---|---|
| Metadata | Read | mandatory, auto-selected |
| Contents | Read & write | branches, commits, spec PRs |
| Pull requests | Read & write | opens the agent PR |
| Issues | Read & write | ticket comments, dequeue |
| Commit statuses | Read & write | `agent-ops/code-judge` status on PR heads |
| Actions | Read & write | `ticket-intake` dispatches `implement.yml` |
| **Workflows** | **No access** | deliberate — see below |
| Variables | Read & write | only if you use `budget-guard.yml` to flip `AGENT_OPS_PAUSED` itself (distinct from "Actions") |

**Organization permissions**

| Permission | Level | Why |
|---|---|---|
| Projects | Read & write | only if queue claims move onto an org project board; Projects v2 sits outside repo scope and needs this explicitly |

An App granted `organization_projects: write` **overrides per-project base-role settings**, which is not how PATs behave. If your project board has restricted roles, the App bypasses them — decide that consciously.

**Do not grant Workflows: write.** For `pull_request` events GitHub evaluates the workflow from the merge commit, so a workflow edited on an agent's own branch takes effect. Withholding this permission makes it *physically impossible* for the App to modify `.github/workflows/`, which is a stronger guarantee than a path guard. Pair it with adding `.github/**` to `guards/<repo>.paths` for every product repo.

## 3. Private key

Bottom of the App settings page → Generate a private key → downloads a `.pem`. Note the **Client ID** from the top of the same page.

## 4. Install

Install App → **Only select repositories**: `agent-ops`, your product repos, and `internal-docs`.

**Not `sales-ops`** (or any repo that only needs read). Installation permissions are per-App, so installing there would grant Contents write to a repo that only needs read. Keep one fine-grained read-only PAT for `SALES_OPS_RO_PAT`, or move the prospect-name list into `agent-ops` and drop that PAT entirely.

Run [`install-preflight.yml`](../.github/workflows/install-preflight.yml) afterwards: it mints a token per repo and reports which installs are missing before a real run 404s.

## 5. Secrets and variables

Set these **on `agent-ops` only** — repo-level, not org-level.

| Name | Kind | Value |
|---|---|---|
| `BOT_APP_CLIENT_ID` | repo **variable** | Client ID from the App settings page |
| `BOT_APP_PRIVATE_KEY` | repo **secret** | entire `.pem` contents, including the `-----BEGIN`/`-----END` lines |

The Client ID is not secret, so making it a variable keeps the secret list down to the one thing that actually matters.

**Why not org-wide:** an org secret is readable by every workflow in every repo it's visible to, and any of those workflows could mint a token with the *full* installation permissions (the down-scoping below is chosen by the caller, not enforced by the secret). An org-wide key would mean an agent working in a product repo could mint a full-permission token across every installed repo. Essentially every token-minting workflow lives in `agent-ops`, which agents never write to — keep it there. If a second repo genuinely needs it, use an org secret with **"Selected repositories"** visibility listing exactly those repos; never "All repositories."

**Later upgrade:** move `BOT_APP_PRIVATE_KEY` into a **GitHub Environment** secret with protection rules. Environment secrets are only readable by jobs that declare `environment:`, and the environment can require approval or restrict branches — which closes the escalation path structurally rather than by convention.

## 6. Bot git identity

Without the App's noreply email, commits render as an unlinked grey avatar with no profile, which makes agent authorship hard to audit.

```
user.name  = example-app-bot[bot]
user.email = <APP_ID>+example-app-bot[bot]@users.noreply.github.com
```

`<APP_ID>` is the numeric ID of the bot account: `gh api '/users/example-app-bot%5Bbot%5D' --jq '.id'`. It is set once in [`.github/actions/bot-identity/action.yml`](../.github/actions/bot-identity/action.yml) (and as the default in `strip-attribution`); use that composite in every workflow that writes commits.

## 7. Workflow wiring

Keep token minting **inline, not in a composite**. The `permission-*` inputs have no documented "none" value — you withhold a permission by omitting the key — so a generic passthrough composite risks either erroring on an empty input or silently granting more than intended. Inline blocks put the grant where a reviewer reads it.

### Mint profiles

**Product repos** — used by `implement.yml`, `code-judge.yml`.

```yaml
- uses: actions/create-github-app-token@v2
  id: bot
  with:
    app-id: ${{ vars.BOT_APP_CLIENT_ID }}
    private-key: ${{ secrets.BOT_APP_PRIVATE_KEY }}
    owner: <YOUR_ORG>
    repositories: example-app-core,example-app-service
    permission-contents: write
    permission-pull-requests: write
    permission-issues: write
    permission-statuses: write
```

**Internal docs, read-only** — used by task agents.

```yaml
    repositories: internal-docs
    permission-contents: read
```

**Internal docs, write** — used by `spec-draft.yml`, `dream.yml`.

```yaml
    repositories: internal-docs
    permission-contents: write
    permission-pull-requests: write
```

**Agent-ops state commits** — ledger, queue, provenance.

```yaml
    repositories: agent-ops
    permission-contents: write
```

**Agent-ops workflow dispatch** — `spec-draft-orchestrator.yml`. A `GITHUB_TOKEN` dispatch starts a run, but that run's completion never fires `workflow_run` (GitHub's anti-recursion rule), so the drain chain needs an App token for this one call.

```yaml
    repositories: agent-ops
    permission-actions: write
```

### Worked example — the re-mint before push

A token minted at job start is dead by the time a long agent run finishes.

```yaml
jobs:
  implement:
    runs-on: ubuntu-latest
    steps:
      # checkout, with a token that only needs to survive the clone
      - uses: actions/create-github-app-token@v2
        id: bot-read
        with:
          app-id: ${{ vars.BOT_APP_CLIENT_ID }}
          private-key: ${{ secrets.BOT_APP_PRIVATE_KEY }}
          owner: <YOUR_ORG>
          repositories: example-app-core
          permission-contents: write

      - uses: actions/checkout@v4
        with:
          repository: <YOUR_ORG>/example-app-core
          token: ${{ steps.bot-read.outputs.token }}
          persist-credentials: false     # don't bake a token that will expire
          fetch-depth: 0

      - uses: ./.github/actions/bot-identity

      # the long part: agent works, builds, tests. Can exceed 1 hour.
      - name: Run implementer
        run: ...

      # fresh token, minted immediately before it is used
      - uses: actions/create-github-app-token@v2
        id: bot-push
        with:
          app-id: ${{ vars.BOT_APP_CLIENT_ID }}
          private-key: ${{ secrets.BOT_APP_PRIVATE_KEY }}
          owner: <YOUR_ORG>
          repositories: example-app-core
          permission-contents: write
          permission-pull-requests: write

      - name: Push and open PR
        env:
          GH_TOKEN: ${{ steps.bot-push.outputs.token }}
        run: |
          git remote set-url origin \
            "https://x-access-token:${GH_TOKEN}@github.com/<YOUR_ORG>/example-app-core.git"
          git push origin "$BRANCH"
          gh pr create --repo <YOUR_ORG>/example-app-core --head "$BRANCH" \
            --title "$TITLE" --body-file pr-body.md
```

---

## Gotchas worth knowing rather than discovering

**Installation tokens expire after 1 hour.** The exec job can run longer. Mint once for checkout and again immediately before push. This is the single most likely thing to fail confusingly on first use.

**`persist-credentials: false` is doing real work.** By default `checkout` writes the token into `.git/config`, so a later `git push` silently reuses the expired job-start token. Turning it off forces an explicit remote URL with a fresh token.

**`x-access-token` is the required username** for an App installation token in an HTTPS remote. The password is the token; the username is that literal string.

**App-authored pushes trigger workflows**, unlike `GITHUB_TOKEN`. That is what you want — canonical CI runs on agent PRs. It is also why the default token would not work here.

**The App can open PRs but cannot approve them** or satisfy a required-review rule. Agents cannot merge themselves, by construction.

**Tokens auto-revoke** in a post-step, so the two tokens in a job do not linger past it.

---

## Verification

1. Secrets land → `cost-digest.yml` and `schema-validate.yml` flip from "not configured" to green.
2. First bot commit → author renders as **example-app-bot** with the App avatar in the PR commit list. Grey/unlinked means the noreply email did not match.
3. `code-judge` posts an `agent-ops/code-judge` commit status on a product-repo PR head → confirms the statuses permission and the cross-repo installation.
4. `install-preflight.yml` reports every expected repo as installed.
