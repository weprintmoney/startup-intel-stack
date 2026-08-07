---
title: "Touch 3 — LinkedIn Connection Request"
description: "Day 9 LinkedIn connection note shell. Founder voice. Hard 300-character limit. Sent manually — never automated."
owner: ""
status: template
last_reviewed: "2026-08-06"
sequence_touch: 3
day_offset: 9
channel: linkedin
sender_voice: founder
---

# Touch 3 — LinkedIn Connection Request

> **HARD RULE:** only claims from `docs/04-marketing/content-ops/claims-vetted.md` may appear in this template or in generated drafts.

## Channel note

This is a LinkedIn connection request note — hard 300-character limit. Not an email. The enrollment agent generates the note text only; **the actual connection request must be sent manually** by the sending persona (LinkedIn automation violates ToS).

**Agent output:** generate the note text and post it as an action item to the configured notification channel (see `channels` in `company-profile.yaml`) with:
- Contact LinkedIn URL
- The personalized note text (≤280 characters — leave buffer for LinkedIn rendering)
- The reminder: "Send LinkedIn request manually from {{sender_name}}'s profile"

## Agent personalization instructions

**Tone:** direct. Acknowledge the email touch without guilt-tripping. One sentence on why connecting makes sense *for them*, not just for you.

**Do not:**
- Say "I've emailed you twice" — don't remind them
- Use pitch language — this is a connection request, not a sales email
- Exceed 280 characters

## Note shell — agent customizes on `{{icp_segment}}`

*Instantiate one variant per ICP segment. Placeholder shape:*

```
Hi {{first_name}} — sent you a note on {{company_name}}'s [their relevant
surface area]. Building [your product, 5-8 words, claims-vetted framing]
for [this segment]. Would love to connect.
— {{sender_name}}
```

Target ~150–200 characters so the personalized fill never breaks the limit.

## Action-item format

The enrollment agent posts:

```
LinkedIn connect — {{first_name}} {{last_name}}, {{contact_title}} at {{company_name}}
Profile: {{linkedin_url}}

Note to send:
"{{note_text}}"

Send manually from {{sender_name}}'s LinkedIn account. Do not automate.
```
