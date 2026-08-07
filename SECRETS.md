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
| `RESEND_API_KEY` | outbound send | `sending.provider: resend` |
| `RESEND_FROM` | from-address | a configured `send_domain` (never the primary domain) |
| `IMAP_HOST` / `IMAP_USER` / `IMAP_PASSWORD` | reply monitoring | the send mailbox must exist |
| `WARMUP_SEED_ADDRESSES` | warmup ramp | comma-separated seed list |

## Rules

- Never commit a secret value anywhere in the repo, including docs and lead files.
- Rotate any key that ever appears in a workflow log.
- The template repo itself needs no secrets — agents only run in instance repos.
