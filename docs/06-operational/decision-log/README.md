---
title: "Decision Log"
description: "Chronological record of load-bearing decisions with the why. Prevents re-litigation of settled questions. One dated file per decision."
owner: ""
status: template
last_reviewed: "2026-08-06"
---

# Decision Log

Chronological record of load-bearing decisions with the *why*. Prevents re-litigation of settled questions — agents and humans both read this before proposing changes to anything it covers. Any change to positioning, pricing, ICP, or strategy must add an entry here **before** merging.

## File convention

One file per decision: `YYYY-MM-DD-short-slug.md` (kebab-case slug, decision date).

Start from [`TEMPLATE.md`](TEMPLATE.md).

## Frontmatter schema

```yaml
---
title: "Short, plain-English statement of what was decided"
description: "One-line context for grep/AI lookup"
owner: "@github-handle"
status: "approved | superseded | deprecated"
last_reviewed: "YYYY-MM-DD"
decision_date: "YYYY-MM-DD"
impacts:
  - "path/to/affected/file.md"
---
```

Body covers four sections: **context** (why now), **decision** (what), **why** (rationale + alternatives considered), **impact** (consequences + affected docs/agents).

## When to add an entry

- Positioning, messaging, or ICP changes
- Pricing model or tier changes (mandatory — see `docs/03-commercial-revenue/pricing.md`)
- Rubric structural changes (adding/removing criteria or disqualifiers)
- GTM strategy pivots
- Any change another team member (or a future agent run) would need to understand in order to not reverse it

## Superseding a decision

Never edit history. Write a new entry, set the old entry's `status: superseded`, and link both ways.

## Current decisions

| Date | Decision | Status | Owner |
|------|----------|--------|-------|
| — | *(none yet — your first entry goes here)* | — | — |

Keep this table current: newest first, one row per entry. Agents may read this table as an index instead of globbing the folder.
