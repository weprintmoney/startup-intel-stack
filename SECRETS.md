# Secrets

GitHub Actions secrets per instance repo. Set with `gh secret set NAME -R <owner>/<repo>`. Keys belong to the company running the instance — founders bring their own accounts. Every workflow skips gracefully (green no-op) when a secret it needs is absent, so set only what your tier uses.

## Required (all tiers)

| Secret | Powers | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | every agent | the only hard requirement; ~$30–100/mo typical |

## Recommended (all tiers)

| Secret | Powers | Without it |
|---|---|---|
| `EXA_API_KEY` | semantic search in signals + enrichment | degrades to plain web search |
| `SLACK_WEBHOOK_URL` | notifications (digests, alerts, reply notices) | agents skip notifying |

## Content ops (seed+, optional quality boosters)

| Secret | Powers | Without it |
|---|---|---|
| `OPENAI_API_KEY` | AEO checks against ChatGPT | AEO monitoring covers fewer engines |
| `PERPLEXITY_API_KEY` | web-grounded AEO checks | same |

## Lead pipeline (seed+)

| Secret | Powers | Without it |
|---|---|---|
| `APOLLO_API_KEY` | lead crawling + enrichment | crawler skips; use event-ingest instead |
| `HUNTER_API_KEY` | email finding fallback | enrichment relies on Apollo only |
| `ATTIO_API_KEY` / `AIRTABLE_API_KEY` | CRM backend (match `crm.provider`) | `crm.provider: none` uses local JSONL store |

## Sending (series-a tier only)

| Secret | Powers | Prerequisite |
|---|---|---|
| `RESEND_API_KEY` / `SENDGRID_API_KEY` / `MAILGUN_API_KEY` | outbound send | match `sending.provider` in company-profile.yaml |
| `SEND_FROM` | from-address override | optional; default is `outreach@{company.send_domain}` |
| `CRM_BCC_ADDRESS` | bcc every send to the CRM for logging | optional |
| `IMAP_HOST` / `IMAP_USER` / `IMAP_PASSWORD` | reply monitoring | the send mailbox must exist |
| `WARMUP_SEED_ADDRESSES` | manual warmup fallback | comma-separated seed list; `sending.warmup_ramp_days` ramps the real send path automatically, this is a separate one-shot tool |

## Notifications (optional, any tier)

Two ways to get alerts; pick one, or both. Everything above prefers `SLACK_WEBHOOK_URL` and only needs the bot token for the DM-a-specific-person alerts below.

| Secret | Powers |
|---|---|
| `SLACK_WEBHOOK_URL` | posts to one fixed channel (the `channels.slack_webhook_secret` name in company-profile.yaml) |
| `SLACK_BOT_TOKEN` | also enables DM-ing a specific person by Slack user ID, for the alert-routing repo variables below |

These are repo **variables**, not secrets (`gh variable set NAME`, not `gh secret set`) — none of them are sensitive:

| Variable | Powers | Requires |
|---|---|---|
| `HEARTBEAT_ALERT_CHANNEL` | where pipeline-heartbeat alerts land | — |
| `DELIVERABILITY_ALERT_CHANNEL` / `DELIVERABILITY_ALERT_UID` | deliverability hard-stop alerts | UID needs `SLACK_BOT_TOKEN` |
| `REPLY_MONITOR_OWNER_UID` / `REPLY_MONITOR_ESCALATION_UID` | DM on every reply / on non-unsubscribe replies | `SLACK_BOT_TOKEN` |
| `SLACK_SALES_REVIEW_CHANNEL` | team channel for reply + soft-bounce notices | — |
| `TEST_SEND_RECIPIENT` | who format-test-send.yml is allowed to send to | required to use that workflow at all |
| `HEARTBEAT_SKIP` | comma-separated workflow filenames to mute pre-launch | — |

## Rules

- Never commit a secret value anywhere in the repo, including docs and lead files.
- Rotate any key that ever appears in a workflow log.
- The template repo itself needs no secrets — agents only run in instance repos.
