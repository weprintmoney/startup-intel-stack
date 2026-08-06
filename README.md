# Startup Intel Stack

GTM-in-a-box: an agentic go-to-market system for early-stage startups, run entirely from a GitHub repo + Claude Code + GitHub Actions.

This repo is a **template**. One instance per company. All company-specific parameters live in `company-profile.yaml`; docs are the single source of truth (SSOT) that every agent reads; agents run on GitHub Actions crons and commit their output back as dated files or PRs.

## What you get

| Layer | What it does |
|-------|--------------|
| **Docs SSOT** (`docs/`) | Positioning, messaging, ICP, personas, brand voice, sales playbook, sequences, pricing skeleton, decision log |
| **Content ops** (`docs/04-marketing/`) | Blog/KB drafting, AEO gap monitoring, competitive signals, topic-cluster health |
| **Sales pipeline** (`agents/`) | Lead crawl → dedup → pre-filter → enrich → stack-profile → qualify (rubric-gated) → sequence enrollment → copy evaluation → send, with human approval via PR merge before any email goes out |
| **Feedback loop** | Monthly agent mines your edits to approval PRs and proposes rubric/template improvements |
| **Onboarding** (`/gtm-init`) | Interactive setup: ingests your existing docs or scrapes your website/LinkedIn/X to draft the SSOT docs for your correction |

## Stage tiers

Set `stage:` in `company-profile.yaml`. Agents check the tier and skip anything above it.

| Tier | Enabled |
|------|---------|
| `pre-seed` | Positioning/ICP docs, decision log, weekly market signals, brand voice |
| `seed` | + content ops pipeline, sales sequences, lead pipeline (crawl→qualify), warmup |
| `series-a` | + full outbound sending, nurture, deliverability monitoring, docs drift review |

## Cost floor

Designed to degrade gracefully when API keys are absent:

- **Minimum:** Anthropic API key only (~$30–100/mo). Signals, content drafts, doc maintenance all work.
- **Recommended (seed+):** + Resend (free tier, 100 sends/day cap enforced), Exa (signal enrichment).
- **Optional:** Apollo (lead sourcing), Hunter (email finding), CRM API (Attio/Airtable — abstracted in `lib/`).

## Getting started

1. Create your repo from this template (keep it **private** — it will hold lead data).
2. Open the repo in Claude Code and run `/gtm-init`.
3. Answer the interview (or point it at your website/LinkedIn/X to draft answers for you).
4. Add secrets it tells you to add, merge the setup PR, and the crons take over.

## Hard rules (non-negotiable, enforced in workflows)

1. Human approval (PR merge) required before any first email to a contact.
2. Suppression-list check before every send.
3. Pause a contact's sequence the moment they reply.
4. Respect the global `SEQUENCES_PAUSED` flag and the daily send cap.
5. Never send from your primary domain — use a send subdomain/alt domain.
6. No named prospects in any public or shared repo — lead data stays in this private instance.
