# Rule: doc frontmatter schema

Every `.md` doc under the numbered domain folders (`docs/01-` through `docs/06-`), including account docs under `docs/03-commercial-revenue/accounts/<slug>/`, must carry YAML frontmatter per this schema. `CLAUDE.md` files are exempt.

## Core fields (every doc)

| Field | Notes |
|---|---|
| `title` | Human-readable title. |
| `description` | One-line summary. Used for grep, search, and AI lookup. |
| `owner` | GitHub handle of the single accountable person, from `company-profile.yaml` → `people[]`. Template docs ship with `owner: ""` — fill on instantiation. |
| `status` | One of `template`, `draft`, `review`, `approved`, `shipped`, `archived`, `superseded`, `stale`. Freshly instantiated docs move `template` → `draft`. |
| `last_reviewed` | `YYYY-MM-DD`. Bump on substantive edit. |

## Optional fields (when they apply)

| Field | When used |
|---|---|
| `author` | When the drafter is distinct from the long-term `owner`. |
| `source_url` | Originating doc (meeting transcript, external doc, article) when content was captured from elsewhere. |
| `tags` | Free-form list for cross-cutting topics. Don't duplicate folder semantics. |

## Doc-type-specific fields

Docs with a defined type add their own fields — examples in this repo:

- Decision-log entries: `decision_date`, `impacts` (see `docs/06-operational/decision-log/README.md`)
- Sequence templates: `sequence_touch`, `day_offset`, `channel`, `sender_voice` (see `docs/03-commercial-revenue/sequences/`)
- Account call summaries: `call_date`, `account`, `participants`

## What is NOT in frontmatter

- **Body content:** decision rationale, notes, metric values — these belong in the doc body.
- **Path-derived facts:** `doc_type`, `domain`, `account` when the folder already encodes it.
- **Company parameters:** anything that belongs in `company-profile.yaml` (names, thresholds, schedules) — reference it, don't copy it.

## Example

```yaml
---
title: "Positioning Architecture"
description: "Master positioning framework — segments, personas, value props."
owner: "@founder-handle"
status: "approved"
last_reviewed: "2026-01-15"
---
```

## When creating or editing a doc

- **Creating:** populate frontmatter immediately. Never commit a body-only file.
- **Editing:** bump `last_reviewed` on substantive edits. Update `status` when it moves.
- **Author ≠ owner:** if you draft a doc someone else owns long-term, fill `author` with your handle and `owner` with theirs.
