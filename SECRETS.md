# Secrets

GitHub Actions secrets per instance repo. Set with `gh secret set NAME -R <owner>/<repo>`. Keys belong to the company running the instance — founders bring their own accounts. Every workflow skips gracefully (green no-op) when a secret it needs is absent, so set only what your tier uses.

## Required (all tiers)

| Secret | Powers | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | every agent | the only hard requirement; ~$30–100/mo typical |

## Recommended (all tiers)

| Secret | Powers | Without it |
|---|---|---|
| `EXA_API_KEY` (or `EXA_AI_API`) | semantic search in signals, enrichment, Apify company-URL resolution, and the AEO fallback engine | degrades to plain web search. Workflows read `secrets.EXA_API_KEY || secrets.EXA_AI_API`, so either name works |
| `SLACK_WEBHOOK_URL` | notifications (digests, alerts, reply notices) | agents skip notifying |

## Content ops (all modes, optional quality boosters)

| Secret | Powers | Without it |
|---|---|---|
| `OPENAI_API_KEY` | AEO checks against ChatGPT | AEO monitoring falls back to Exa (if set) or WebSearch and marks the engine column accordingly |
| `PERPLEXITY_API_KEY` | web-grounded AEO checks | same |

## Lead pipeline (find-leads and up)

| Secret | Powers | Without it |
|---|---|---|
| `APIFY_API_KEY` | `apify-ingest.yml` — Apify actors: public-page LinkedIn people search and company-employees, Google Maps company discovery, Indeed job-posting signals, Meetup events (`lib/apify.py` also accepts the older name `APIFY_TOKEN`) | apify-ingest skips (green no-op) |
| `PROSPEO_API_KEY` | email finding in enrichment — LinkedIn URL → verified email (1 credit per found email, none on a miss). Tried first when set; best fit for LinkedIn-sourced leads | enrichment tries Apollo/Hunter if present, else marks leads `not_found` |
| `APOLLO_API_KEY` | Apollo people search in the crawler, `people/match` email fallback, LinkedIn company-URL resolution | crawler skips; enrichment relies on Prospeo |
| `HUNTER_API_KEY` | last email-finder fallback | enrichment relies on Prospeo (and Apollo if set) |
| `ATTIO_API_KEY` / `AIRTABLE_API_KEY` | CRM backend (match `crm.provider`) | `crm.provider: none` uses local JSONL store |

## Sending (find-and-draft mode only)

> **Not needed when `sending.provider: manual`.** Manual instances email nothing from CI: approved drafts become `sends/manual/<date>-send-packet.md` plus one GitHub issue per lead, and a human sends from their own mailbox and LinkedIn. Every secret in this table stays unset and every send-path workflow exits green at its provider gate.

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
