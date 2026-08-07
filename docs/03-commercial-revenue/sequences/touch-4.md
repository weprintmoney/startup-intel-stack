---
title: "Touch 4 — Final Email"
description: "Day 15 final email shell. Sales voice. Short, easy to reply to. One direct question — not a full pitch."
owner: ""
status: template
last_reviewed: "2026-08-06"
sequence_touch: 4
day_offset: 15
channel: email
sender_voice: sales
---

# Touch 4 — Final Email

> **HARD RULE:** only claims from `docs/04-marketing/content-ops/claims-vetted.md` may appear in this template or in generated drafts.

## Role in the sequence

Day 15. Last touch of the cold sequence. Its only job is to make replying easy — even "not the right time" or "not relevant" closes the loop, and both are valuable outcomes. Any reply pauses the sequence and routes to a human.

## Agent personalization instructions

**Tone:** short, direct, no pressure.

**Goal:** ONE simple question that gets a yes, a no, or a redirect. All three are useful.

**Personalization discipline (copy-evaluator compliance):**
- ≤2 em-dashes in the finished email
- Sourced claims only — every prospect fact traces to the enrichment record
- `{{contact_title}}` verbatim

**Do not:**
- Re-pitch the product
- Reference touches 1–3 explicitly ("I've sent you a few emails...")
- Use scarcity or urgency language ("last chance", "final outreach")
- Exceed 80 words

## Template shells

**Default:**

```
Subject: {{company_name}} + [your product] — worth a look?

Hi {{first_name}},

Quick note. [One sentence restating the single relevant idea for
{{company_name}}, claims-vetted framing.] Curious if this is on your
radar or if the timing's off.

Either way, would love to hear your read on where {{company_name}} is
headed with this.

[Sign-off], {{sender_name}}
{{sender_title}}, {{company_name_own}}

If this isn't relevant, reply "unsubscribe" and I'll remove you right away.
```

**Alternate — "wrong time?" (use when touch-1 and touch-2 show zero open signals):**

```
Subject: Is this the wrong time?

Hi {{first_name}},

I've sent a couple of notes about [topic, 4-6 words] for {{company_name}}.
If the timing's off or this isn't the right fit, just let me know. Happy
to reconnect when it makes sense.

If there's a better person to talk to about [their relevant function],
a quick redirect would be great.

[Sign-off], {{sender_name}}
{{sender_title}}, {{company_name_own}}

If this isn't relevant, reply "unsubscribe" and I'll remove you right away.
```

**Alternate — proof hook (use when the lead's segment cares about a vetted, cite-able proof point):**

```
Subject: [vetted proof point, ≤60 chars]

Hi {{first_name}},

One more note. [1-2 sentences: the vetted proof point and its link,
straight from claims-vetted.md.]

If [topic] is relevant to what {{company_name}} is building, I'd love
20 minutes.

[Sign-off], {{sender_name}}
{{sender_title}}, {{company_name_own}}

If this isn't relevant, reply "unsubscribe" and I'll remove you right away.
```

## Selection guidance for the agent

Use the **default** unless:
- Zero opens on touch-1 and touch-2 → "wrong time?" alternate
- Lead segment/persona maps to a vetted proof point → proof-hook alternate
