---
title: "Sales Playbook"
description: "Discovery motion, objection-handling framework, and sender-persona guidance. Generic skeleton — instantiate with your ICP, pains, and proof points."
owner: ""
status: template
last_reviewed: "2026-08-06"
---

# Sales Playbook

Skeleton playbook. Fill in from `docs/01-market-intelligence/` (ICP, personas, positioning) and `docs/04-marketing/content-ops/claims-vetted.md` (the only source of product claims). Named accounts never appear here — per-account context lives in `accounts/<slug>/`.

## Sales methodology

State your motion in one line, in this shape:

> **Lead with [the operational pain your ICP feels daily] → Discover [the deeper requirement that justifies switching] → Close with [your defensible differentiator].**

### Core process

1. **Qualify** — confirm the lead uses (or will use) your product category and hits your ICP thresholds
2. **Discover** — operational pain, requirements, decision process
3. **Demo/Prove** — technical or business proof matched to the discovered pain
4. **Negotiate** — value-based, tied to business outcomes (pricing rules: see `pricing.md`)
5. **Close** — risk mitigation and differentiation vs. the status quo

---

## Discovery framework

Time-boxed structure for a 30-minute discovery call. Write 3–5 questions per block from your ICP doc.

### Opening qualification (5 minutes)

**Objective:** confirm ICP fit before investing discovery time.

- [Question confirming category usage or intent]
- [Question identifying current solution/vendor]
- [Question quantifying scale against `icp.company_size` / your usage thresholds]
- [Question surfacing the segment-defining attribute from your ICP]

**Disqualifiers** (end gracefully if hit — mirror `icp.disqualifiers`):
- [No usage or plans in your category]
- [Below minimum viable scale with no growth trajectory]
- [Segment explicitly excluded by the ICP]

### Pain discovery (10 minutes)

**Objective:** understand current limitations and frustrations. One sub-block per pain pillar from your positioning doc:

**[Pain pillar 1 — e.g., cost/scale]:**
- [Open question about their biggest challenge in this area]
- [Quantifying question — spend, headcount, incident frequency]

**[Pain pillar 2 — e.g., capability gap]:**
- [Question surfacing whether they've hit the specific failure mode you fix]

**[Pain pillar 3 — e.g., operational burden]:**
- [Question about engineering time / process cost of the status quo]

### Requirement discovery (10 minutes)

**Objective:** uncover the deeper requirement (compliance, customer demand, procurement gate) that turns pain into a budgeted project.

- [Question about external constraints — frameworks, audits, customer security/procurement reviews]
- [Question about deals or initiatives blocked by the status quo]
- ["What would happen if [the failure mode] occurred?" — quantifies stakes]

### Decision-process discovery (5 minutes)

**Objective:** map the buying committee and timeline.

- "Who else would be involved in evaluating this?"
- "What's driving the timeline?"
- "What would need to happen for you to make a change?"

---

## Objection-handling framework

Pattern: **objection → reframe → proof.** Acknowledge the objection honestly, reframe to the axis where you win, then offer proof — and every proof point must come from `claims-vetted.md`. Never trash-talk competitors (copy-evaluator D4 applies to spoken pitch too).

| Objection | Reframe | Proof (claims-vetted only) |
|---|---|---|
| "We're happy with our current solution" | Acknowledge what works; probe for the growth-stage pain they haven't hit *yet* | [Vetted case study or benchmark] |
| "This sounds like it adds [cost/complexity/latency]" | Name the tradeoff honestly, then show the measured reality | [Vetted metric with citation] |
| "We can't afford another vendor/system to manage" | Reframe to operational simplicity — what it replaces or removes | [Vetted deployment-simplicity claim] |
| "We're building this ourselves" | Respect the ambition; probe timeline realism and permanent maintenance cost | [Vetted time-to-production comparison, if any] |
| "We need to evaluate other options first" | Welcome it; offer the comparison criteria that favor your differentiator | [Vetted comparison content] |
| "[Segment-specific objection]" | [Reframe] | [Proof] |

Add rows as objections recur. The monthly feedback loop should mine lost-deal notes for new rows.

---

## Sender-persona guidance

Outbound identity maps to `company-profile.yaml` → `people[]` entries with `sender_persona: true`.

| Persona | `people[].role` | Voice | Used for |
|---|---|---|---|
| Founder voice | `founder` | Peer-to-peer, opinionated, technical depth | Touch-1, touch-3, nurture; strategic accounts |
| Sales voice | `sales` | Professional, methodical, benefit-led | Touch-2, touch-4; process-driven follow-ups |

Rules:
- If no `sales`-role sender exists, the founder sends all touches — vary the *tone* per the sequence files, not the identity.
- Never send under a persona whose `sender_persona` is false or whose `people[]` entry is missing — the enrollment agent must fail loudly, not guess.
- When a sender departs or changes, update `company-profile.yaml` first; sequences read it at runtime.

---

## Cross-references

- ICP + personas: `docs/01-market-intelligence/`
- Vetted claims (the only proof source): `docs/04-marketing/content-ops/claims-vetted.md`
- Qualification gates: `rubrics/`
- Outbound copy: `sequences/`
- Pricing: `pricing.md` (changes gated by decision log + founder review)
