---
title: "Site Messaging Map — persona × section × frame"
description: "Production checklist mapping every site section to its primary/secondary personas and the SSOT frames that belong there. Turns the messaging house into a concrete site copy plan."
owner: ""
status: template
last_reviewed: "2026-09-12"
---

# Site Messaging Map

## Purpose

The messaging house (`01-market-intelligence/positioning.md`, `buyer-personas.md`) defines *what* you say to *whom*. This doc is the operational layer: **which section on which page carries which frame, for which persona**.

Use it when writing or reviewing site copy. Every homepage section, every product-page section, every solutions page has a **primary persona** whose voice it speaks in, one or more **secondary personas** it also has to serve, and one or more **anchor frames** from the messaging house that must appear.

## Design principles

1. **Homepage voice is single-persona where possible.** Pick the one buyer your homepage speaks to first — usually your primary champion, not "everyone." Other personas arrive via side doors (search, comparison pages, solutions pages), not the homepage cold.
2. **Every section has one primary voice, even when it also serves other personas.** A secondary-persona reader scrolling past a primary-persona hero should still find a block that speaks *to them* further down — written for them, not generically.
3. **Concept-based nav, not persona-based nav.** Product / Solutions / Docs / About — not "For Developers / For Security." Personas find their concept; they don't have to self-select their role.
4. **Avoid dedicated per-persona bounce pages unless the volume justifies them.** A well-placed section on the homepage plus a targeted solutions page usually covers a secondary persona without the maintenance cost of a whole page.
5. **Every frame in the messaging house has a home.** If a frame from your positioning docs doesn't appear anywhere on the site, either the frame is a gap or the site is a gap. This map surfaces both.

## Persona × entry-path (where each persona shows up)

Fill in from `buyer-personas.md` — one row per persona, with their most common cold entry point and secondary entries.

| Persona | Buyer role | Most common cold entry | Secondary entries |
|---|---|---|---|
| _(primary champion persona)_ | Primary champion, decision-maker | `/` | |
| _(technical evaluator persona)_ | Technical evaluator | | |
| _(gatekeeper/compliance persona)_ | Gate; must approve | | |
| _(economic buyer persona)_ | Economic buyer | | |

## Homepage (`/`)

Primary voice: _(fill in)_. Every section speaks to that persona first; sections marked with secondary personas serve them in-place, not on a separate page.

| Section | Primary persona | Secondary personas | Anchor frame(s) from SSOT | Notes |
|---|---|---|---|---|
| **Hero** (H1 + lede) | | — | | |
| **Why-now / problem framing** | | | | |
| **Outcomes / mechanism** | | | | |
| **Proof / comparison** | | | | |
| **Use cases** | | | | |
| **Third-party validation** (if any) | | | | |
| **Deploy / how it works** | | | | |
| **Final CTA** | | | | |

**Homepage frames NOT in scope** — belong elsewhere: list the frames from your messaging house that deliberately live on a solutions page or product page instead of the homepage, and where.

## Solutions / product pages

Repeat the per-page table above for each solutions or product page you maintain. Keep this doc as the single source of truth for "which persona owns which section" — when site copy and this map disagree, update whichever one is wrong; don't let them drift.
