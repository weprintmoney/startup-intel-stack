---
title: "Touch 2 — Concrete Pain Point"
description: "Day 4 follow-up shell. Sales voice. One concrete, segment-specific scenario the product solves. Short — 3-4 sentences. Structure only."
owner: ""
status: template
last_reviewed: "2026-08-06"
sequence_touch: 2
day_offset: 4
channel: email
sender_voice: sales
---

# Touch 2 — Concrete Pain Point

> **HARD RULE:** only claims from `docs/04-marketing/content-ops/claims-vetted.md` may appear in this template or in generated drafts.

## Role in the sequence

Day 4. Assumes touch-1 was read (even if it wasn't). Escalates from framing to a tangible scenario: if touch-1 named the gap, touch-2 makes it concrete with a scenario or a vetted metric.

## Agent personalization instructions

**Tone:** professional, methodical, gets to the point. Not peer-to-peer — this is the sales persona (`people[]` entry with `role: sales` and `sender_persona: true`; if none exists, the founder sends with this tone).

**Goal:** ONE concrete, specific example of a problem your product solves for their segment.

**Length:** 80–120 words. 3–4 short paragraphs. Subject line is a direct benefit statement.

**Personalization discipline (copy-evaluator compliance):**
- ≤2 em-dashes in the finished email
- Sourced claims only — every prospect fact traces to the enrichment record
- `{{contact_title}}` verbatim; never invent seniority

**Do not:**
- Recap touch-1 or say "I wanted to follow up"
- Reuse touch-1's framing
- Lead with your feature — lead with their scenario or outcome

## Segment scenarios — agent selects on `{{icp_segment}}`

*Instantiate one scenario block per ICP segment. The agent rewrites in its own words. Placeholder shape:*

**[segment-slug] (example — replace):**
> Subject: [direct benefit statement for this segment, ≤60 chars]
>
> [2–3 sentences: a concrete scenario this segment hits — the moment the status quo fails them. Specific and recognizable, not abstract.]
>
> [1–2 sentences: what your product does about it, claims-vetted only. If you have a vetted metric, this is where it earns its keep.]

## Closer shell (all segments)

```
[One light ask, one sentence. Example shape: "Worth a 20-minute call to see
if there's a fit?"]

[Sign-off], {{sender_name}}
{{sender_title}}, {{company_name_own}}

If this isn't relevant, reply "unsubscribe" and I'll remove you right away.
```
