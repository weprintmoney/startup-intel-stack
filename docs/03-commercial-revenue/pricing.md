---
title: "Pricing"
description: "Intentionally empty pricing skeleton. Pricing changes require a decision-log entry and founder review — no agent may write pricing content here."
owner: ""
status: template
last_reviewed: "2026-08-06"
---

# Pricing

**This file is intentionally empty of numbers.** It ships as a skeleton because pricing is the most consequential, most drift-prone content in the repo.

## Hard rule

Any change to this file — adding tiers, changing numbers, altering packaging — requires **both**:

1. A dated decision-log entry in `docs/06-operational/decision-log/` (context, decision, why, impact), merged in the same PR.
2. Review by the founder (`people[]` entry with `role: founder`) — enforce via CODEOWNERS on this path.

Agents must **never** write, infer, or repeat pricing in any outbound content. The copy-evaluator rubric (D5) hard-fails drafts that mention pricing or commercial terms.

## Skeleton (fill in when you set pricing)

### Pricing model

- [Model: seat / usage / capacity / flat / hybrid — and why]

### Tiers

| Tier | Who it's for | What's included | Price |
|---|---|---|---|
| [Tier name] | [ICP segment] | [Capabilities] | [—] |

### Packaging rules

- [What's never unbundled, what's always included, discount floors, term rules]

### Commercial guardrails

- [Who can approve non-standard terms; escalation path]
