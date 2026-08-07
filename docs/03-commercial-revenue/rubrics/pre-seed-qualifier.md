---
title: "Pre-Seed Qualifier Rubric"
description: "Relaxed qualifier variant for leads that are themselves pre-seed companies — no production stack, no public evidence yet. Re-weights toward timing, vertical fit, and reachability."
owner: ""
status: template
last_reviewed: "2026-08-06"
---

# Pre-Seed Qualifier Rubric

**Pass threshold:** `icp.qualification_thresholds.pre_seed_pass` from `company-profile.yaml` (relaxed vs `standard_pass` because pre-seed companies lack public evidence).
**Applies to:** All leads where `icp_segment: "pre-seed"`.

---

## Overview

Pre-seed prospect companies are fundamentally different from the standard ICP: they have no production stack, no public case studies, no hiring track record, and no pain evidence yet. The standard rubric's B and C categories would zero-score almost every pre-seed lead. This rubric re-weights toward what IS knowable at pre-seed:

1. **Timing** — Did they just raise? The window before they lock architecture/vendor decisions is short.
2. **ICP fit by vertical + product signal** — Will they plausibly need what you sell?
3. **Reachability** — Can you reach the technical founder?

---

## Category E — Disqualifiers (run first, any hit = FAIL)

| Code | Criterion | Notes |
|------|-----------|-------|
| E1 | Company is a known competitor | Check `competitors` in `company-profile.yaml` + suppression list |
| E2 | Company is already in active pipeline or closed-lost | Check CRM |
| E3 | Outside `icp.geographies` with no compliant outreach path | `country_code: UNKNOWN` → ESCALATE, not FAIL |
| E4 | Not a product company — pure consulting, agency, or thin wrapper with no original software product | Reject if no original product |

Retiring or adding a disqualifier requires a decision-log entry in `docs/06-operational/decision-log/`.

---

## Category A — ICP Fit (max 40 pts)

| Code | Criterion | Points |
|------|-----------|--------|
| A1 | Company is building a product that will plausibly need your category. *(Generic example: for ACME AI, "the announcement describes a workflow product that will need automated routing.")* | 20 |
| A2 | Vertical match against `icp.verticals` | 10 |
| A3 | Scout classified the lead against a specific product/offering of yours (`target_product` set) | 10 |

**A-score:** sum of applicable points.
**Note:** the standard rubric's anti-ICP veto based on absent stack evidence does NOT apply here. Absence of a stack is expected at pre-seed and not penalized.

---

## Category B — Pain Evidence (max 20 pts)

At pre-seed there is rarely explicit pain evidence. Score what exists.

| Code | Criterion | Points |
|------|-----------|--------|
| B1 | Announcement or founder post explicitly names the problem your product solves | 15 |
| B2 | Vertical strongly implies the requirement your product addresses (per the ICP doc's vertical → requirement mapping) | 10 |
| B3 | Founder has prior experience at a company that used your product category (LinkedIn evidence) | 5 |

Maximum 20. Multiple hits: take highest applicable; do not double-count B1+B2 for the same signal.

---

## Category C — Reachability (max 20 pts)

| Code | Criterion | Points |
|------|-----------|--------|
| C1 | Technical founder name found (not blank) | 10 |
| C2 | LinkedIn URL found for the contact | 5 |
| C3 | Email found (deliverable) | 5 |

**Note:** at pre-seed it's acceptable to proceed with LinkedIn-only outreach if email is not found. C3 is not a blocking criterion.

---

## Category D — Timing (max 30 pts)

Timing is the **primary** signal for pre-seed. A lead outside the window is not worth pursuing — they'll have made their architecture and vendor decisions.

| Code | Criterion | Points |
|------|-----------|--------|
| D1 | `funding_date` ≤ 30 days ago | 30 |
| D2 | `funding_date` 31–45 days ago | 20 |
| D3 | `funding_date` 46–60 days ago | 10 |
| D4 | `funding_date` > 60 days ago or missing | 0 |

`funding_date` is **required** on all pre-seed leads (enforced by the scout agent). A missing date scores D4 = 0 and almost certainly fails the rubric.

---

## Scoring

```
normalized_score = round((A + B + C + D) / 110 * 100)
```

(Max raw: 40 + 20 + 20 + 30 = 110)

| Decision | Condition |
|----------|-----------|
| PASS | normalized_score ≥ `pre_seed_pass` AND zero Category E hits |
| ESCALATE | normalized_score within 5 points below `pre_seed_pass`, OR any soft-escalation flag (e.g., `country_code: UNKNOWN`) |
| FAIL | normalized_score more than 5 points below `pre_seed_pass`, OR any hard Category E hit |

---

## Output schema (same as the standard qualifier-critic)

```json
{
  "lead_email": "string",
  "company_name": "string",
  "decision": "PASS | FAIL | ESCALATE",
  "normalized_score": 0,
  "category_scores": {"A": 0, "B": 0, "C": 0, "D": 0},
  "failing_criteria": ["D4"],
  "disqualifier_hits": [],
  "reason": "one sentence — the decisive factor",
  "rubric_version": "pre-seed",
  "timestamp": "ISO-8601"
}
```
