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

Fill every field in `company-profile.yaml`. Interview for what scraping can't give you.

**Mode comes first — it gates everything downstream.** Never ask "what stage are you?" and never present the words pre-seed/seed/series-a: plenty of instances are not venture-backed startups at all, and a fundraising label tells you nothing about how much of the system they want on. Ask what they want the system to *do*, and say what each answer costs:

> Three ways to run this. Which sounds right to start?
> 1. **Research and writing only** — it keeps your positioning, ICP, personas and brand voice current, and watches your market and competitors. Doesn't touch contact data. Needs nothing but an Anthropic key.
> 2. **Find leads too** — it also finds people matching your ICP every week, enriches them, and scores them against your rubric, so you get a qualified list. It does *not* write outreach. Needs a contact source (see below).
> 3. **Find leads and draft outreach** — it also writes the outreach for each qualified lead and opens it for your approval. Nothing sends until you approve it. Needs a contact source, plus either an email provider or the willingness to send by hand (`sending.provider: manual` — the system compiles approved drafts into a copy-paste packet and one GitHub issue per lead; nothing is ever emailed by CI).

Map the answer to `company.mode`: 1 → `docs-only`, 2 → `find-leads`, 3 → `find-and-draft`. You can always change it later.

**Be honest about the contact source before they pick 2 or 3.** The crawler sources contacts from the Apollo.io API (`APOLLO_API_KEY`, a paid subscription), or failing that reads a contact-list CSV they export themselves to `leads/raw/`. With neither, the crawl runs, finds nothing, and exits clean — a silent empty pipeline. Say this plainly at the point they choose, not later. If they have neither yet, recommend starting at `docs-only` and moving up when a source is in place, or point them at `event-ingest.yml` for a one-off attendee/member list they already have.

**Also flag if their targets aren't reachable this way.** Apollo indexes people by company and job title. If their ICP isn't "a role at a company" — individual investors, family offices, private buyers, consumers — say so directly: the crawler will not find those, and a list they source themselves fed through `event-ingest.yml` is the honest path. Don't let them configure a mode whose lead sourcing can't work for their targets.

**Is the market a metro or region rather than a country?** A local services business, a regional practice, a city-bound venue. If yes, fill `icp.locations` — metro name, the suburbs that count (`aliases`), how far out is still "local" (`radius_miles`), and whether a company headquartered elsewhere but with a staffed local office counts (`include_remote_hq_with_local_office`). Also record the exact `apollo_location` string Apollo uses for that metro. Leave the list empty for a national or global ICP; every metro rule in the pipeline switches off when it is empty.

Then the rest:
- sending: `resend` / `sendgrid` / `mailgun` with a dedicated send domain (must NOT be the primary domain), or `manual` (no domain, no provider — humans paste from `sends/manual/` and tick touches on `lead` issues). `manual` is the right answer for anyone sending a few dozen emails a month from their own mailbox.
- sender personas (who is willing to have email go out under their name)
- disqualifiers and geographies (EU → LinkedIn-only routing)
- CRM: none / airtable / attio (`none` is a real answer — it uses a local file, zero setup)
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

## Phase 4 — Enable the chosen mode

1. Set cron schedules in workflows from `cadences:` (stagger from defaults if asked).
2. List the GitHub secrets the chosen mode needs, by exact name, and tell them to add each one themselves in the repo's Settings → Secrets and variables → Actions. **Never ask anyone to paste a key into the chat** — it would land in the transcript. Offer `gh secret set NAME` (which prompts for the value without echoing it) as the alternative for anyone comfortable in a terminal.
   - every mode: `ANTHROPIC_API_KEY`
   - `find-leads`+: a contact source (`APOLLO_API_KEY`, paid) unless they're supplying their own CSV; optional `EXA_API_KEY`, `HUNTER_API_KEY`, CRM key
   - `find-and-draft`: an email provider key matching `sending.provider`, plus `IMAP_*` for reply monitoring — **or nothing at all when `sending.provider` is `manual`**
   Full table: `SECRETS.md`.
3. Disable (comment out cron) workflows above the mode.
4. Verify branch protection on main. The approval gate does not depend on it — agents write drafts to a branch and open a PR regardless — but branch protection is what stops anyone, human or agent, from pushing queue files straight to main and bypassing review.

## Phase 5 — Setup PR

Open a PR containing everything from Phases 2–4. PR body: checklist of secrets to add, docs marked `draft` needing review, and what to expect in week one. The founder merging this PR is the go-live event.

Spell out what "running" will actually look like in their mode, so a quiet week doesn't read as a broken system:
- `docs-only`: signal and content files land as dated commits/PRs. No contact data, ever.
- `find-leads`: the crawl chain runs weekly and leaves a scored list in `leads/critic/`. **It stops there — no outreach is written.** Say this explicitly; otherwise the first quiet week looks like failure.
- `find-and-draft`: the same chain continues into drafted outreach and opens an approval PR. Nothing sends until that PR is merged. First batch is deliberately small.

If they have no contact source configured, say plainly that the weekly crawl will find nothing until they add one — don't let them discover it as silence.

## Hard rules during onboarding

- One question at a time; prefer drafting-for-correction over interrogation.
- Never copy another company's claims, pricing, or named customers into this instance.
- Never ask anyone to paste an API key, password, or token into the chat.
- If the founder asks to skip approval gates or send caps: refuse and explain rule 5 in CLAUDE.md.
- Don't let someone leave onboarding configured for a mode that can't work for them — no contact source in `find-leads`, no send domain in `find-and-draft` (unless `sending.provider` is `manual`), or an ICP the crawler structurally can't reach. Say so at the point they choose.
