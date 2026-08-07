# Vetted Claims

> **THE ONLY** product claims agents may make without flagging for review. Every claim not on this list must be wrapped in a `> CLAIM TO VERIFY:` blockquote in the draft and surfaced at the top of the PR description.

> **SETUP NOTE (founder):** This file starts empty on purpose. Add every claim you are willing to defend publicly, have a technical owner review each line, then remove this notice. Agents HALT content generation while this notice is present — a wrong claim here becomes a wrong claim in published content.

## How to add a claim

- One claim per row. Short, declarative, unambiguous.
- Every claim should be defensible from a published source (your docs, README, press release) or an internal doc in `docs/`. If it lives only in someone's head, it doesn't go here.
- Compliance claims cite the certification actually held, or are phrased as "designed for X" + "not yet certified."
- Customer/partner names require a linkable public reference (press release, joint announcement) AND per-piece approval — note that in the Conditions column.

## Vetted claims

| Claim | Source | Added | Conditions |
|-------|--------|-------|------------|
|       |        |       |            |

## What agents may NOT say without verification (defaults — edit to fit)

- Specific performance numbers (latency, throughput, accuracy) — these change; require technical-owner sign-off per piece
- Specific compliance certifications — only certifications actively held
- Customer or partner names — only publicly referenceable ones, with per-piece approval
- Pricing or commercial terms
- Roadmap items — never write about unreleased features

## Retired claims — never publish

When positioning changes (a pivot, a deprecated product line, a corrected error), retired phrases go here so agents stop using them even when they're still technically true. Keep this list in sync with any CI checks on your public site.

| Retired phrase | Why | Say instead |
|----------------|-----|-------------|
|                |     |             |

## Competitor claims — universal rule

Any claim about a competitor requires:

1. A citation to the competitor's own source (docs, changelog, pricing page, official blog, public benchmark)
2. The access date, written inline
3. Phrasing as "as of [date], [Competitor] [does/doesn't] [thing] per [their docs]"

No exceptions. If you can't cite it, don't write it.

## When an agent wants to make a claim that's not on this list

Wrap the sentence(s) in the draft:

```
> **CLAIM TO VERIFY:** [exact claim] — [why you believe it's true / source if any]
```

The PR description must list every CLAIM TO VERIFY block at the top so the human reviewer can resolve them.
