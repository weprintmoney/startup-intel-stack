---
title: "Qualifier-Critic Rubric"
description: "Adversarial-evaluator rubric for scoring enriched leads before they reach the human review queue. 24 criteria, 5 categories (A7 metro presence active only when icp.locations is set). Pass threshold comes from company-profile.yaml."
owner: ""
status: template
last_reviewed: "2026-09-20"
doc_version: "1.1"
---

# Qualifier-Critic Rubric

## Purpose

Evaluates enriched lead JSON objects before human review. Flags probable non-fits early. Default posture: **reject unless the case is overwhelming.** Runs as a separate-context evaluator sub-agent after enrichment completes — the evaluator must not share context with the agent that produced the lead.

The critic does not replace human review. It raises the floor of what reaches the human queue: the founder becomes the *final* reviewer, not the *first* filter.

**Bump `doc_version` in the frontmatter on any substantive change** (new/removed criteria, changed point weights, changed scoring formula) — `agents/qualifier-critic/CLAUDE.md` declares the version it was calibrated against, and `scripts/check_doc_version.py` fails the run before scoring if this doc has moved without a matching CLAUDE.md update.

## Scoring thresholds

All thresholds come from `company-profile.yaml` → `icp.qualification_thresholds`. **Never hardcode a number here.**

- **Pass:** normalized score ≥ `standard_pass` AND zero Category E disqualifier hits
- **Fail:** normalized score < `standard_pass` OR any Category E disqualifier triggers
- **Escalate:** within 5 points below `standard_pass` (border cases) — send to the pipeline owner with full scoring detail
- **Auto-fail category-level:** any pipeline configuration that could send without explicit human approval — stop, fix the guardrail first

## Structure

24 criteria in 5 categories:

| Category | Focus | Criteria | Max points |
|---|---|---|---|
| A | ICP segment fit | 7 (6 scored + 1 veto) | 50 when `icp.locations` is set (A7 active); 42 otherwise |
| B | Pain-point evidence | 5 | 35 |
| C | Reachability | 4 | 26 |
| D | Timing signals | 4 | 28 |
| E | Disqualifiers | 4 hard-fails | 0 (binary veto) |

---

## Category A — ICP segment fit (7 criteria, 50 pts with A7 / 42 without)

Segments, verticals, sizes, and buyer titles come from `company-profile.yaml` → `icp` and the ICP doc in `docs/01-market-intelligence/`.

| # | Criterion | Description | Weight | Evidence required | Scoring |
|---|---|---|---|---|---|
| A1 | Segment classification | Lead operates in one of the ICP segments defined in `icp.verticals` / the ICP doc | 10 | ≥2 independent signals from enrichment (`industry`, `company_description`) or from the lead's profile record at confidence ≥ 60 (`leads/stack-profiles/` or `leads/org-profiles/`, per `icp.profile_agent`). Cite the fields. | Pass/fail — if no segment applies, fail |
| A2 | Primary-segment validation | If lead matches the primary segment: segment-defining attributes are explicitly present, not inferred. *(Generic example: "ACME AI's primary segment is multi-location logistics SaaS — the enrichment must show multiple locations or a SaaS product, not just the word 'logistics.')* | 9 | Segment-defining fields populated (e.g., `customer_count`, `product_type`) OR description explicitly matches. | 0–9. Partial evidence scores roughly half. |
| A3 | Secondary-segment validation | If lead matches a secondary segment: the quantitative or qualitative trigger for that segment is present (size threshold, stated cost pain, growth signal). | 8 | Specific field or quoted phrase + date. Vague industry inference = low score. | 0–8. Vague = 3. Specific = 8. |
| A4 | Regulated/constrained-segment validation | If lead is in a segment defined by an external constraint (compliance framework, procurement regime, certification): the constraint is explicitly named. "Security is important to us" is NOT sufficient. | 9 | Named framework/constraint in enrichment OR a discovery quote. | 0–9. One named constraint + intent = 6. Two+ or an audit/procurement trigger = 9. |
| A5 | Existing-customer pattern match (bonus) | Lead resembles the profile of an existing paying customer (size, segment, use case). Bonus, not veto — absence costs nothing at early stage. | 6 | `company_size`, `funding_stage`, `product_description` classify into a known-won cohort. | 0–6. Strong match = 6. Weaker = 3. None = 0. |
| A6 | Anti-ICP rejection (veto) | Hard veto if the lead matches any pattern in `icp.disqualifiers` — e.g., no real need for the product category, an adequate-for-them cheaper substitute, or no technical owner who could adopt. | 0 | Check `company_description` / `discovery_notes` / `hiring_breakdown`. Cite the disqualifying statement. | Hard veto. Any match = auto-fail, escalate with reason code. |

| A7 | Metro presence | **Active only when `icp.locations` in `company-profile.yaml` is non-empty.** The contact and/or the company are inside the configured metro. | 8 | `metro_match` and `metro_evidence` on the lead record; profile field `metro_presence` at confidence ≥ 60 when an org-context profile exists. | Contact in metro at a metro-HQ company = 8. Contact in metro, HQ elsewhere with `local_office` evidence = 6. HQ in metro but contact remote or location unknown = 3. `metro_match: unknown` with no evidence = 0. |

**Subtotal:** 50 max with A7 active (A1–A5 + A7 scored; A6 veto-gate); 42 max when `icp.locations` is empty and A7 is skipped.

---

## Category B — Pain-point evidence (5 criteria, 35 pts)

| # | Criterion | Description | Weight | Evidence required | Scoring |
|---|---|---|---|---|---|
| B1 | Primary buyer trigger | Evidence of the #1 pain your product resolves, as defined in the ICP doc. *(Generic example: for ACME AI, "a prospect's ops team flagged manual dispatch as their scaling blocker.")* | 10 | Exact quote from `discovery_notes` / transcript / thread with date + source. Traceable to the lead's own statement. | 0–10. Specific quote + date = 10. Inferred from industry only = 4. None = 0. |
| B2 | Cost/performance pain | Stated cost, performance, or operational pain in the problem space. | 8 | `enrichment.pain_points` or discovery containing a specific pain phrase. Cite phrase + source + date. | 0–8. Quantified pain = 8. Vague = 3. |
| B3 | External-constraint trigger | Industry inherently subject to the constraint your product addresses, OR an explicit statement that the constraint bit them (audit finding, lost deal, procurement block). | 8 | `industry` field OR quote from discovery. | 0–8. Industry alone = 5. Industry + explicit mention = 8. |
| B4 | Freshness / recency | Pain evidence dated within 90 days. Triggered by recent funding, hiring, launch, incident, customer win/loss. | 7 | `enrichment.event_date` ≤ 90 days before the run date, OR discovery call within 30 days. | <30d = 7. 30–90d = 5. 90–180d = 2. >180d = 0. |
| B5 | Buyer-persona fit | Title matches a primary buyer persona in `icp.buyer_titles`. Secondary personas score lower. | 2 | `lead_title` from enrichment. | Primary = 2. Secondary = 1. Non-buyer = 0. |

**Subtotal:** 35 max.

---

## Category C — Reachability (4 criteria, 26 pts)

| # | Criterion | Description | Weight | Evidence required | Scoring |
|---|---|---|---|---|---|
| C1 | Email validity | Verified deliverable; not on a disposable/known-bad domain. | 10 | `email_verified` true OR recent send success. | Pass/fail — bouncing = hard blocker. |
| C2 | Role authority | Title indicates budget/decision authority for this purchase (Head of, VP, C-level, Director). Not: IC, analyst, intern. | 10 | `lead_title`. Explicit authority = 10. Ambiguous (senior IC at a very small company) = 5. IC = 0. | 0–10. |
| C3 | Company existence verified | Real, operating, searchable in public records. Rule out dissolved, personal projects, acquired-and-shut. | 4 | Company LinkedIn / registry / website populated and verified active. | Fail if dissolved. Else pass. |
| C4 | Referrer network (bonus) | Referred by an existing customer, analyst, partner, or public procurement doc. | 2 | `referral_source`. Customer/partner referral = 2. Webinar/content = 1. None = 0. | 0–2. |

**Subtotal:** 26 max.

---

## Category D — Timing signals (4 criteria, 28 pts)

The four signals below assume a software buyer. Instances selling to a different buyer may re-weight D to the timing signals that matter there (for example a new People leader, a return-to-office change, a new local office) — keep the 28-point total, bump `doc_version`, and record the change in the decision log.

| # | Criterion | Description | Weight | Evidence required | Scoring |
|---|---|---|---|---|---|
| D1 | Recent funding | Round closed within 90 days. Signals budget + hiring. | 8 | `funding_date` within 90d OR announcement link. Cite round + date. | <30d = 8. 30–90d = 6. >90d = 0. |
| D2 | Recent leadership hiring | A buyer-persona role posted or hired in the last 60 days. | 8 | `hiring_signal` field. Job link + post date OR lead mention. | Primary-persona hire = 8. Adjacent leadership = 6. Generic hiring = 2. |
| D3 | Recent product launch / pivot | New product, replatform, or pivot in the problem space in the last 90 days. Signals active evaluation. | 7 | `product_launch_date` OR announcement (blog, press, social). Cite date + link. | <90d = 7. 90–180d = 4. >180d = 0. |
| D4 | RFP / procurement signal | Active RFP, procurement, or "evaluating solutions" statement in the last 30 days. | 5 | `rfp_status` field OR discovery statement. | Active RFP = 5. "Evaluating options" = 3. None = 0. |

**Subtotal:** 28 max.

---

## Category E — Disqualifiers (4 hard-fails, 0 pts)

Binary. **ONE hit = overall fail**, regardless of other scores. Populate specifics from `company-profile.yaml` → `icp.disqualifiers` and `competitors`.

| # | Disqualifier | Description | Evidence | Trigger |
|---|---|---|---|---|
| E1 | Suppression list hit | Lead email or company on the do-not-contact list (prior churn, complaint, unsubscribe). | `suppression_list_match` true OR CRM history. | Fail + note reason. |
| E2 | Competitor employee | Works for a company in `competitors` (as employee, not customer). | LinkedIn OR `company_name` matches a competitor entry. | Fail. |
| E3 | Geography without outreach path | HQ/operations outside `icp.geographies` with no compliant outreach channel. Note: EU contacts route to LinkedIn-only per the repo's universal rules — that is a routing change, not always a fail. **When `icp.locations` is set:** `metro_match: none` (contact and company both outside the metro, no local office evidence) with no compliant alternative is a fail. | `company_headquarters_country` + `company_operations`; `metro_match` + `metro_evidence`. | Fail (escalate — often recoverable via channel routing or a local-office finding). |
| E4 | Decision-maker publicly opposed | Founder/CEO has publicly rejected the product category, or built a competing in-house alternative they champion. | Public post / blog / talk. Cite statement + source. | Fail + escalate to the sales owner for relationship assessment. |

**Category E:** Pass = zero hits. Fail = any single hit. Retiring or adding a disqualifier requires a decision-log entry in `docs/06-operational/decision-log/`.

---

## Scoring calculation

**Total available:** 139 points when A7 is active (A: 50 + B: 35 + C: 26 + D: 28); 131 points when `icp.locations` is empty and A7 is skipped (A: 42 + B: 35 + C: 26 + D: 28). E is a binary veto-gate.

**Normalization:** `final_score = (A + B + C + D) / 139 × 100` with A7 active; `/ 131 × 100` without. State which denominator was used in the verdict's `reason` when it matters.

**Pass threshold:** normalized score ≥ `icp.qualification_thresholds.standard_pass` AND all Category E pass.

---

## Workflow

1. Load lead JSON from the enrichment stage output.
2. Run **Category E first.** Any trigger → fail immediately, escalate to human with reason code (E1–E4).
3. Score A–D. For each criterion, consult the evidence-required column. Absent evidence → score 0. Never infer.
4. Calculate normalized score.
5. Decision:
   - ≥ `standard_pass` AND E pass: **PASS** → human review queue
   - < `standard_pass` OR E fail: **FAIL** → auto-reject, log to the rejected-leads log
   - Within 5 points below `standard_pass` AND E pass: **ESCALATE** to the pipeline owner with full detail

## Output schema

```json
{
  "lead_email": "sam@example-prospect.com",
  "company_name": "Example Prospect Inc",
  "decision": "PASS | FAIL | ESCALATE",
  "normalized_score": 73.4,
  "category_scores": { "A": 38, "B": 28, "C": 24, "D": 21 },
  "failing_criteria": ["B2_cost_pain_stale", "C2_role_authority_insufficient"],
  "disqualifier_hits": [],
  "reason": "one sentence — the decisive factor",
  "rubric_version": "standard",
  "timestamp": "ISO-8601"
}
```

---

## Notes for the evaluator LLM

- **Persona matches are soft**, not veto. An unusual title influencing the right budget at a strong-fit company still scores.
- **Freshness matters:** stale pain (>180d) drops Category B dramatically. Recent Category D signals can offset.
- **Escalate, don't reject, on borderline scores.** Human judgment on ambiguous segments is faster than re-running enrichment.
- **Absent evidence scores zero.** The critic's job is to be the skeptic the generator can't be.

## Maintenance

The monthly feedback-loop agent proposes edits to this rubric based on human overrides in the review queue. Threshold changes go in `company-profile.yaml`, not here. Structural changes (adding/removing criteria, retiring a disqualifier) require a decision-log entry.

## Version notes

- **1.1 (2026-09-20):** A7 metro presence added (active only with `icp.locations`); E3 extended for `metro_match: none`; A1/B4 evidence generalised to the lead's profile record (`icp.profile_agent`).
- **1.0 (2026-08-06):** template baseline.
