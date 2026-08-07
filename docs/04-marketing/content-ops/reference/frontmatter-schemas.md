# Frontmatter Schemas by Content Type

> **SETUP NOTE (founder):** If your site has build-time content schemas (e.g., Astro Content Collections, Contentlayer), reconcile this file against them — a mismatch fails your site build when a draft is published. If you have no schemas yet, these are a sensible default to build from. Remove this notice once reconciled.

## Conventions

- Drafts live under `docs/04-marketing/content-ops/drafts/`; published content lives at `channels.blog_path` from `company-profile.yaml`
- Slugs: kebab-case, no dates, no stop words ("a", "the", "and"), ≤60 chars
- Dates in ISO 8601 (`2026-05-04`)
- Tags from the controlled vocabulary in `./taxonomy.md` — do NOT invent tags

## Blog posts → `drafts/queue/`

```yaml
---
title: # 50-60 chars, primary keyword in first 30 chars
description: # 140-155 chars, includes primary + 1 secondary keyword
pubDate: # set on publish
updatedDate: # omit on first publish
author: # team byline or a named person from company-profile.yaml people
heroImage: # optional
category: # one of: engineering, industry, company (edit to fit your site)
tags: # 3-5 from taxonomy.md
contentType: pillar # or: reactive
primaryKeyword:
secondaryKeywords: [list of 3-5]
targetPersona: # a persona id from docs/01-market-intelligence/buyer-personas.md
wordCount:
sources: # all URLs cited inline
internalLinks: # 3-5 of your own URLs referenced in the piece
aeoQuotableBlock: | # the 1-2 sentences most likely to be cited by an LLM, copied VERBATIM from the lead
canonicalUrl: # leave blank unless syndicated
draft: true # ALWAYS true — a human flips it on publish
---
```

## Knowledge base / FAQ articles → `drafts/faq/`

```yaml
---
title: # phrased as a question OR a clear entity definition: "What is X?"
description: # 140-155 chars, direct answer to the title question in first 100 chars
pubDate:
updatedDate:
category: # one of: concepts, architecture, compliance, integrations, comparisons (edit to fit)
tags: # 3-5 from taxonomy.md
primaryEntity: # the THING this article defines
relatedEntities: [list of 3-5] # for the entity graph / related content
targetPersona: # KB skews toward the technical/builder persona
sources:
internalLinks:
aeoQuotableBlock: |
faqSchema: true # signals the site template to render FAQPage JSON-LD
draft: true
---
```

## Comparison pages → `drafts/queue/`

```yaml
---
title: # "[Your product] vs [Competitor]: [Differentiator Angle]" — 50-60 chars
description: # 140-155 chars, lead with the reader's actual decision
pubDate:
updatedDate:
competitor: # exact name as they market themselves
competitorUrl: # their canonical homepage
comparisonAngle: # your differentiation axis (e.g., deployment, pricing model, compliance)
tags: # includes exactly one vs-<competitor> tag
targetPersona: # comparisons skew toward the buyer/executive persona
sources: # CRITICAL — every competitor capability claim must have a citation
internalLinks:
aeoQuotableBlock: |
comparisonTable: true # signals the site template to render a structured comparison
draft: true
---
```

## Validation rules

Before writing the file, the agent must check:

- `title` length is 50-60 characters
- `description` length is 140-155 characters
- slug (filename) is kebab-case, ≤60 chars
- `tags` are all in `./taxonomy.md`
- `draft: true` is set
- `aeoQuotableBlock` is copied verbatim from the post body, not paraphrased

If any check fails, fix it before committing. Do not ship invalid frontmatter.
