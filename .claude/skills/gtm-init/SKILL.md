---
name: gtm-init
description: Interactive onboarding for a new Startup Intel Stack instance. Interviews the founder or scrapes public sources (website, LinkedIn, X) to fill company-profile.yaml, draft the docs/ SSOT, and open the setup PR. Use when setting up this repo for a new company or re-running setup after major changes.
---

# /gtm-init — GTM Stack Onboarding

Walk a founder from empty template to running system. Work in phases; confirm at each gate before moving on. Never invent facts about the company — everything you draft gets explicitly confirmed or corrected by the founder.

## Phase 0 — Preflight

1. Confirm this repo was created from the template and is **private**. If public, stop and warn: lead data will live here.
2. Check `gh auth status`. Confirm which GitHub account owns the instance.
3. Ask the single highest-leverage question first: **"Do you have existing positioning/ICP docs, or should I draft them from your public footprint?"**

## Phase 1 — Source material

**Path A (has docs):** ask for paths/uploads (positioning, ICP, pitch deck notes, pricing if any). Read them all before drafting.

**Path B (scrape):** gather from public sources, in this order of trust:
1. Company website (all pages — product, pricing, about, blog)
2. LinkedIn company page + founder posts (last ~90 days)
3. X/Twitter account posts (last ~90 days)
4. Anything else the founder points at (docs sites, GitHub org, press)

Extract: what the product does, for whom, differentiators, competitors mentioned, tone of voice, evidence of ICP (who engages, case studies, logos).

## Phase 2 — company-profile.yaml

Fill every field in `company-profile.yaml`. Interview for what scraping can't give you:
- stage (pre-seed / seed / series-a) — this gates everything downstream
- send domain (must NOT be the primary domain)
- sender personas (who is willing to have email go out under their name)
- disqualifiers and geographies (EU → LinkedIn-only routing)
- CRM: none / airtable / attio
- daily cap and send window (defaults are safe; confirm)

Show the completed YAML. Gate: founder approves before Phase 3.

## Phase 3 — Draft the SSOT

Draft in this order (each grounds the next). Every doc gets frontmatter and `status: draft`:
1. `01-market-intelligence/positioning.md` — value pillars, segments, one-liner
2. `01-market-intelligence/icp.md` — expanded from the YAML criteria, with reasoning
3. `01-market-intelligence/buyer-personas.md` — JTBD, pains, objections, hooks per title
4. `01-market-intelligence/competitive-landscape.md` — from `competitors:` list + scraping
5. `02-brand/voice.md` — inferred from their existing public copy; banned-phrase list started
6. `03-commercial-revenue/sales-playbook.md` — discovery motion + objection handling
7. `03-commercial-revenue/sequences/` — 4-touch shells, personalization tokens, ZERO unvetted product claims
8. `04-marketing/content-ops/claims-vetted.md` — start empty; explain that agents may only use claims listed here

Present drafts as **"here's what I inferred — correct me"**, one doc at a time for the load-bearing three (positioning, ICP, voice); batch the rest.

## Phase 4 — Enable the stage tier

1. Set cron schedules in workflows from `cadences:` (stagger from defaults if asked).
2. List required GitHub secrets for the chosen tier and how to add each (`gh secret set NAME`). Minimum: `ANTHROPIC_API_KEY`. Seed+: `RESEND_API_KEY`, optional `EXA_API_KEY`, `APOLLO_API_KEY`, CRM key.
3. Disable (comment out cron) workflows above the tier.
4. Verify branch protection on main; approval-PR gate depends on it.

## Phase 5 — Setup PR

Open a PR containing everything from Phases 2–4. PR body: checklist of secrets to add, docs marked `draft` needing review, and first-week expectations (which crons fire when). The founder merging this PR is the go-live event.

## Hard rules during onboarding

- One question at a time; prefer drafting-for-correction over interrogation.
- Never copy another company's claims, pricing, or named customers into this instance.
- If the founder asks to skip approval gates or send caps: refuse and explain rule 5 in CLAUDE.md.
