---
title: "Touch 1 — Cold Open"
description: "Day 0 cold email shell. Founder voice, peer-to-peer. Sets up the gap specific to the lead's use case. Structure only — fill copy blocks from claims-vetted.md."
owner: ""
status: template
last_reviewed: "2026-08-06"
sequence_touch: 1
day_offset: 0
channel: email
sender_voice: founder
---

# Touch 1 — Cold Open

> **HARD RULE:** only claims from `docs/04-marketing/content-ops/claims-vetted.md` may appear in this template or in generated drafts. No product copy ships in this shell — write yours when instantiating.

## Role in the sequence

Day 0. The first thing this person ever reads from you. One job: show you understand *their* specific situation and name the gap your product closes. Peer-to-peer (founder-to-founder or founder-to-technical-leader), not vendor-to-buyer.

## Agent personalization instructions

**Required context before writing:**
1. Read `{{company_description}}` — understand what the company builds and where your product category fits in it.
2. Identify their specific exposure based on `{{icp_segment}}` (see the segment framing section below).
3. Write `{{pain_point}}` as 1–2 sentences in the sender's voice, specific to their situation. No generic phrasing.
4. Close with one light ask (see closer).

**Personalization discipline (copy-evaluator compliance):**
- **Em-dashes:** no more than 2 in the finished email (E3 hard-blocks at 3+). Prefer commas, colons, periods.
- **Sourced claims only:** every fact cited about the prospect must appear in that lead's enrichment record. If it isn't in the record, don't write it. No web-search assertions in the draft.
- **Titles are load-bearing:** use `{{contact_title}}` verbatim. Do not invent seniority ("Head of X" is not "founder").
- **Salutation rule:** if `{{contact_title}}` contains Founder/Co-founder/CEO → peer-opener variant A; if it contains CTO/VP Engineering (or your ICP's technical-leader titles) → peer-opener variant B; otherwise omit the peer opener and go straight to `{{opener_hook}}`.

**Subject line:**
- Pattern: `[their specific product or use case]: [the gap]`
- Must reference something specific from `{{company_description}}`, not a generic phrase
- 45–60 characters; no `!`, no ALL CAPS, no spam triggers

**Length:** 180–220 words max. 4–5 short paragraphs.

## Segment framing — `{{pain_point}}` reference

*Instantiate one guidance block per ICP segment from your ICP doc. The agent selects the block matching `{{icp_segment}}` and rewrites it in its own words for this company. Placeholder example for a fictional company:*

**[segment-slug] (example — replace):**
> [Company]'s product does [segment-defining activity], which means [the specific operational consequence your product addresses]. [Why the status-quo answer falls short in one sentence.] *(Every factual assertion here must be generic to the segment or vetted in claims-vetted.md.)*

## Template shell

```
Subject: {{subject_line}}

Hi {{first_name}},

{{salutation}}{{opener_hook}}

{{pain_point}}

[1–2 sentences: what your product does about that gap, in plain language.
Every claim from claims-vetted.md. One deployment/adoption fact max.]

[Optional: 1 sentence of proof — {{vertical_proof}}, sourced from claims-vetted.md.]

[Light ask, one sentence. Example shape: "Worth 25 minutes? I'd value your
perspective either way."]

[Sign-off], {{sender_name}}
{{sender_title}}, {{company_name_own}}

If this isn't relevant, reply "unsubscribe" and I'll remove you right away.
```

## Token guidance

- **`{{opener_hook}}`** — 1 sentence showing the sender did homework on this person specifically: their background, a public product decision, a post they wrote, or `{{signal}}` (the funding/hiring/launch event that qualified them). Never generic. Every fact must appear in the enrichment record.
- **`{{vertical_proof}}`** — 1 sentence of segment-relevant proof, selected from the vetted-claims list. If no vetted proof exists for the segment, omit — do not improvise.
