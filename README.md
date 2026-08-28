# Startup Intel Stack

GTM-in-a-box: an agentic go-to-market system for early-stage startups, run entirely from a GitHub repo + Claude Code + GitHub Actions.

## What this is

**One shared source of truth** — positioning, ICP, personas, roadmap, brand voice, sales playbook, pricing, sequences. It lives in `docs/`, and every agent reads from it.

**Production loops on top of it:**

- **Outbound** that finds leads, writes hyper-custom sequences, monitors deliverability, and keeps an evergreen nurture running.
- **SEO and AEO** that watch rankings, remediate, generate content, and ship.
- **Launch playbooks.**
- **Intelligence that lands in Slack** — market, competitors, engineering signals, analysts, plus regulatory and CVE monitors that actually match the product line.
- **Conference and CFP tracking** with draft responses already written.

**A self-improving product coding harness.** Tickets that identify themselves. Specs, implementation, review — all autonomous. Then the harness looks at what broke, what drifted, and what should become a rule tomorrow, and implements that.

## How it's built

This repo is a **template**. One instance per company. All company-specific parameters live in `company-profile.yaml`; docs are the single source of truth (SSOT) that every agent reads; agents run on GitHub Actions crons and commit their output back as dated files or PRs.

## Start here

Two audiences land on this repo. Pick your path.

**Running this on your startup?** → [Getting started](#getting-started).
The rest of this README, then `/gtm-init`. You'll fork this repo, run the interview, and have a working L1 SSOT + L2 outbound loop within a day.

**Studying the framework, giving a talk, or evaluating the pattern?** → [`docs/00-foundations/`](docs/00-foundations/) → [`examples/`](examples/).
Read the two field-notes papers first (framework + implementation companion). Then open the two skeletons — a genericized Level 2 loop under [`examples/sales-ops-skeleton/`](examples/sales-ops-skeleton/) and a genericized Level 3 coding harness under [`examples/agent-ops-skeleton/`](examples/agent-ops-skeleton/) — to see the concrete shape of each level. The skeletons are for reading; the template itself is the runnable L1 + L2.

## What you get

| Layer | What it does | Where it lives |
|-------|--------------|----------------|
| **L1 · Docs SSOT** | Positioning, messaging, ICP, personas, brand voice, sales playbook, sequences, pricing skeleton, decision log | `docs/01-` through `docs/06-` |
| **L1 · Content ops** | Blog/KB drafting, AEO gap monitoring, competitive signals, topic-cluster health | `docs/04-marketing/` + workflows |
| **L2 · Sales pipeline (live scaffold)** | Lead crawl → dedup → pre-filter → enrich → stack-profile → qualify (rubric-gated) → sequence enrollment → copy evaluation → send, with human approval via PR merge before any email goes out | `agents/`, `lib/`, `.github/workflows/` |
| **L2 · Feedback loop** | Monthly agent mines your edits to approval PRs and proposes rubric/template improvements | `.github/workflows/feedback-loop.yml` |
| **L2 · Reference (mature)** | Fuller version of the sales pipeline — 23 workflows, kill switch, EU router, deliverability monitor, judge-evals regression harness. Genericized from a live implementation for study, not to run from here. | [`examples/sales-ops-skeleton/`](examples/sales-ops-skeleton/) |
| **L3 · Coding harness (reference)** | The self-improving ticket → spec → implement → review → judge → PR → dream-loop pipeline. Not shipped in this template's live scaffold; open the skeleton to see the shape. | [`examples/agent-ops-skeleton/`](examples/agent-ops-skeleton/) |
| **Foundations** | The two field-notes papers this template implements (framework + phase-by-phase implementation companion) | [`docs/00-foundations/`](docs/00-foundations/) |
| **Onboarding** | Interactive setup: ingests your existing docs or scrapes your website/LinkedIn/X to draft the SSOT docs for your correction | `/gtm-init` |

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

## Secrets

See [SECRETS.md](SECRETS.md). Only `ANTHROPIC_API_KEY` is required; everything else is optional and workflows no-op green without it.

## Syncing with upstream

This template is the upstream for all instances. Generic fixes and new capabilities land here first; instances pull them down. If you improve an agent inside your instance, upstream the generic part of the change here so every instance (including the original system this was extracted from) benefits. Instance-specific content — `company-profile.yaml`, drafted docs, `leads/` — never flows upstream.

## Hard rules (non-negotiable, enforced in workflows)

1. Human approval (PR merge) required before any first email to a contact.
2. Suppression-list check before every send.
3. Pause a contact's sequence the moment they reply.
4. Respect the global `SEQUENCES_PAUSED` flag and the daily send cap.
5. Never send from your primary domain — use a send subdomain/alt domain.
6. No named prospects in any public or shared repo — lead data stays in this private instance.
