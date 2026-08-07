---
title: "Evergreen Nurture — 21-Day Touchpoint"
description: "Stay-in-touch email shell for contacts who completed the cold sequence with no reply. Not a pitch — one relevant update, one soft invitation."
owner: ""
status: template
last_reviewed: "2026-08-06"
sequence_touch: nurture
day_offset: 21
channel: email
sender_voice: founder
---

# Evergreen Nurture — 21-Day Touchpoint

> **HARD RULE:** only claims from `docs/04-marketing/content-ops/claims-vetted.md` may appear in this template or in generated drafts.

## Purpose and rules

This email goes to contacts who:
- Completed the 4-touch cold sequence
- Never replied
- Are not on the suppression list
- Are in a geography with a compliant email path (`icp.geographies`)

**This is not a sales pitch.** It is a lightweight "still here, something relevant happened" note. Goal: top-of-mind awareness, not a new conversion attempt. One relevant update, one soft invitation. No hard ask.

**Cadence:** every 21 days until the contact replies (→ sequence pauses) or 6 months elapse (→ suppress from nurture, mark `nurture_status: dormant` in the CRM).

**Stop trigger:** any reply — even an unsubscribe or "not interested" — stops the nurture immediately.

## Agent personalization instructions

**Each nurture email must reference something that actually happened recently** (pick one):
1. A new product milestone or vetted proof point (from `claims-vetted.md` — check it's current)
2. A newly validated customer segment or use case (from the ICP doc)
3. A relevant industry news item (regulatory update, notable incident, standard change in your space)
4. A new content piece (blog post, case study) relevant to their segment

**Length:** 60–90 words. 2–3 very short paragraphs.

**Tone:** founder voice — peer, not vendor. No urgency. Easy to ignore. Easy to reply to.

## Template shells

**Template A — milestone/update:**

```
Subject: {{company_name}} — quick update on [your product]

Hi {{first_name}},

Wanted to drop a quick note. [1 sentence: the milestone or vetted proof
point, with link if published.]

Given what {{company_name}} is building, I thought you'd find this more
relevant now than when I first reached out.

If the timing's better for a quick call, I'm easy to reach.

[Sign-off], {{sender_name}}
{{sender_title}}, {{company_name_own}}
```

**Template B — relevant news/regulatory item:**

```
Subject: {{vertical_news_subject}}

Hi {{first_name}},

{{vertical_news_hook}} — thought it was relevant given {{company_name}}'s
work in {{icp_segment_plain}}.

[1 sentence: how your product relates, claims-vetted framing.]

Happy to send over more detail if useful.

[Sign-off], {{sender_name}}
{{sender_title}}, {{company_name_own}}
```

`{{vertical_news_subject}}` names the specific item; `{{vertical_news_hook}}` is 1 sentence summarizing it, with a source.

**Template C — content piece (use when a new post directly relevant to their segment was published):**

```
Subject: New post — {{blog_title}}

Hi {{first_name}},

We published a piece this week on {{blog_topic}} — directly relevant to
what {{company_name}} is building.

[{{blog_title}}]({{blog_url}})

Worth a read. Happy to discuss if it raises questions.

[Sign-off], {{sender_name}}
{{sender_title}}, {{company_name_own}}
```

## Template selection guidance

| Condition | Template |
|---|---|
| New milestone/proof point since last contact | A |
| News or regulatory item relevant to their segment | B |
| New relevant content piece | C |
| None of the above | A (default — reuse the current milestone blurb) |

Prefer B or C over A when there's a real news hook — it makes the email feel timely rather than scheduled.

## Unsubscribe footer

Every nurture email must include:

```
---
To stop receiving these emails, click here: {{unsubscribe_link}}
```

The unsubscribe link routes to your send infrastructure's unsubscribe endpoint, which appends the email to the suppression list with `reason: unsubscribed`.
