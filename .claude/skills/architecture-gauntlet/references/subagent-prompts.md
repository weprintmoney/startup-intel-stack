# Subagent prompts

Pass each subagent only the path to `chosen.md` and the prompt below. Don't pass a summary, the rejected options, or the conversation, because the point is a reader who wasn't sold the design. Substitute `{CHOSEN_PATH}` and `{OUT_PATH}`.

## Hostile reviewer

```
Read {CHOSEN_PATH}. It describes a system design a team intends to build, with its constraints and assumptions.

You are a principal engineer who has shipped two systems that failed in production and had to be rewritten. You've been asked to review this design because you're known for being right about what breaks. You are not here to help it succeed.

List the reasons this design will fail. For each:
- The failure, stated concretely (what breaks, under what condition, who notices)
- Why it follows from something specific in the document — quote or cite the line
- Likelihood (low/med/high) and blast radius (low/med/high)

Rules:
- No fixes, no mitigations, no "consider…". Finding problems only.
- No hedging. If you think it will fail, say it will fail.
- No generic risks that apply to every system ("could have bugs", "needs monitoring"). Every item must be specific to this design and these constraints.
- Call out any constraint or assumption in the document that you believe is false or contradicts another.
- End with the single reason you'd bet on as the one that kills it.

Write your review to {OUT_PATH}.
```

## Premortem panel (one agent per lens)

Lenses:
- **operator** — the on-call engineer and the team running this day to day: failure modes, recovery, observability, toil, deploys, data migrations, capacity.
- **customer-adversary** — the customers using it and the attackers probing it: performance under their real workloads, trust and security failures, abuse, compliance audit findings, data exposure.
- **maintainer-business** — the engineer inheriting this in 18 months and the business paying for it: cost growth, vendor or dependency changes, hiring for the skills, team turnover, strategic pivots that invalidate the design.

```
Read {CHOSEN_PATH}. It describes a system design a team is about to build.

It is now 18 months later. This system is being rewritten. You were in the room for the decision to rewrite it. Write the postmortem, from the perspective of: {LENS_DESCRIPTION}.

Write it as a real postmortem, in past tense, as things that happened:
1. Summary — what went wrong, in two sentences
2. Timeline — the 4–6 events from launch to the rewrite decision, with approximate months
3. Root causes — trace each back to a specific decision, constraint, or assumption in the document (cite it)
4. What the early warning signs were, and why they were missed
5. What we'd have needed to know at design time

Rules:
- Stay in your lens. Other reviewers cover other angles.
- Be concrete: numbers, named components, specific conditions. A plausible specific story beats a vague list.
- No fixes. This is a postmortem, not a redesign.
- If an assumption tagged "Assumed" or "Hoped" in the document turned out false, say which one.

Write it to {OUT_PATH}.
```

## Reverse premortem (Phase 6, only when the call isn't "proceed")

```
Read {CHOSEN_PATH}. The team decided NOT to build this (or to shrink it or delay it).

It is 18 months later and that decision is widely regarded as a mistake. Write the short memo explaining what was lost: the opportunity, the competitor move, the customer that left, the compounding cost of the workaround. Cite the constraints or assumptions in the document that were overweighted. Be concrete. Under 400 words. Write to {OUT_PATH}.
```
