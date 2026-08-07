---
title: "Example Account — Structure Reference"
description: "Redacted example showing the per-account folder convention. Copy this structure for each real account. Account data never leaves this private repo."
owner: ""
status: template
last_reviewed: "2026-08-06"
---

# Example Account

> **This is a structure reference, not a real account.** Create one folder per account at `accounts/<account-slug>/`, starting from this layout. Account folders are confidential: never referenced in public repos, shared docs, or issue trackers. Prospect/customer names never appear outside `accounts/` and `leads/`.

## Folder convention

```
accounts/<account-slug>/
├── README.md          # this file — overview, status, key contacts
├── positioning/       # account-specific positioning angle, collab notes
└── content/           # drafts, decks, call notes, follow-ups for this account
    └── calls/         # dated call summaries (YYYY-MM-DD-topic.md)
```

Every doc carries frontmatter (`owner`, `status`, `last_reviewed`). Threads, follow-ups, and roadmap responses belong here — not in the global sales playbook.

---

## Overview

- **Account:** [Account name]
- **Status:** [prospect | evaluating | pilot | customer | churned]
- **Segment:** [which ICP segment, per `docs/01-market-intelligence/`]
- **Owner:** [who on your team owns the relationship]
- **Entry point:** [how they arrived — inbound, sequence, referral, event]

## Key contacts

| Name | Title | Role in deal | Notes |
|---|---|---|---|
| [Redacted] | [Title] | [Champion / economic buyer / blocker] | [Context, with date added] |

## Positioning angle

[1–2 paragraphs: which positioning pillar leads for this account and why. What they care about, what they've explicitly said, what proof resonates. Link to `positioning/` docs for depth.]

## Call notes

Dated summaries live in `content/calls/`. Index the load-bearing ones here:

| Date | Topic | Key outcome |
|---|---|---|
| [YYYY-MM-DD] | [Topic] | [Decision or next step] |

## Open threads

Track every open loop so nothing drops between calls:

- [ ] [Owed to them: e.g., a technical answer, a doc, an intro — with owner + date opened]
- [ ] [Owed by them: e.g., data for evaluation, security questionnaire — with date requested]
- [ ] [Internal: e.g., roadmap question routed to product — link the issue]

## Risks / watch items

- [Anything that could stall or kill the deal, stated plainly]
