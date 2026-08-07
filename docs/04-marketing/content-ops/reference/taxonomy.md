# Content Taxonomy — Controlled Vocabulary

> Every tag used in content frontmatter must come from this file. If you need a tag that doesn't exist, propose it at the bottom with a justification — do NOT invent tags inline.
>
> Tags are organized into beats. Use 3–5 per piece, drawn from at least 2 different beats. Don't stack 5 tags from the same beat — that signals the piece is too narrow or trying to rank for too many things at once.

> **SETUP NOTE (founder):** This is a template. `/gtm-init` drafts beats 1–3 from your `company-profile.yaml` and positioning docs; correct them, then remove this notice. Beats 4 and 5 are generic and usually need only light editing.

---

## Beat 1: Product category & core capabilities

The tags that describe WHAT you build. Derive from `company.one_liner` and `docs/01-market-intelligence/positioning.md` — one tag for the category, one per value pillar / core capability.

| Tag | Use when… |
|-----|-----------|
| `<category-tag>` | Core product category — appears on nearly all posts |
| `<capability-tag-1>` | The piece is about value pillar 1 |
| `<capability-tag-2>` | The piece is about value pillar 2 |

## Beat 2: Buyer problems & use cases

The tags that describe WHY buyers care. Derive from the pains and JTBD in `docs/01-market-intelligence/buyer-personas.md` — one tag per major pain or use case.

| Tag | Use when… |
|-----|-----------|
| `<use-case-tag-1>` | The piece addresses use case / pain 1 |
| `<use-case-tag-2>` | The piece addresses use case / pain 2 |

## Beat 3: Industry / vertical

One tag per vertical in `icp.verticals` (`company-profile.yaml`). Use ONE vertical tag per post, and only when the content is tailored to that industry — tagging all verticals on a generic post is a signal to remove vertical specificity from the piece.

| Tag | Use when… |
|-----|-----------|
| `<vertical-tag-1>` | Content tailored to vertical 1 |
| `<vertical-tag-2>` | Content tailored to vertical 2 |
| `general` | No specific vertical applies |

## Beat 4: Content format / intent

Use exactly one per piece. Drives routing and performance tracking. Generic — keep as is.

| Tag | Use when… |
|-----|-----------|
| `tutorial` | Step-by-step how-to — reader builds something by the end |
| `explainer` | Concept definition — reader understands something by the end |
| `comparison` | Your product vs. a named competitor |
| `opinion` | You take a position on an industry trend or architectural debate |
| `reactive` | Response to news, a release, or an external event — time-sensitive |
| `case-study` | Customer story or worked example with outcomes |
| `benchmark` | Performance data post — requires technical-owner sign-off before publish |

## Beat 5: Competitors (comparison posts only)

One `vs-<competitor>` tag per competitor in `company-profile.yaml`, used only on comparison pages, one per page.

| Tag | Competitor |
|-----|-----------|
| `vs-<competitor-slug>` | (one row per entry in `competitors:`) |

---

## Proposing new tags

Add the tag here with justification before using it in frontmatter. A tag earns a place if it will appear on at least 3 pieces per quarter — one-off topics belong in the post copy, not the taxonomy.

**Proposed additions (not yet approved):**
<!-- format: `tag-name` — why it's needed, estimated frequency -->
