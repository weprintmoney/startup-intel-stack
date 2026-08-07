---
title: "Copy-Evaluator Rubric"
description: "Adversarial-evaluator rubric for scoring outbound email drafts before send. 24 criteria, 5 categories. Pass threshold from company-profile.yaml. Up to 5 iteration rounds."
owner: ""
status: template
last_reviewed: "2026-08-06"
---

# Copy-Evaluator Rubric

## Purpose

Scores outbound email drafts after the sequence-enrollment agent generates them from sequence templates + enrichment context. Runs between generation and send. Up to 5 iteration rounds; if still failing after round 5, escalate to the human reviewer.

**Hard rule (upstream guardrail):** No send without explicit human approval (PR merge). The critic doesn't bypass approval — it raises the floor of what reaches the reviewer.

## Scoring thresholds

All thresholds come from `company-profile.yaml` → `icp.qualification_thresholds`. **Never hardcode a number here.**

- **Pass:** normalized score ≥ `copy_pass` AND zero Category E hard-block hits
- **Fail (< 5 retries):** score < `copy_pass` OR hard-block hit → auto-retry the generator with rubric feedback
- **Escalate (≥ 5 failed attempts):** send to the human reviewer with draft + full scoring log + all attempts

## Structure

24 criteria in 5 categories:

| Category | Focus | Criteria | Max points |
|---|---|---|---|
| A | Voice fidelity | 5 | 35 |
| B | Specificity & personalization | 5 | 35 |
| C | Value clarity & proportionality | 4 | 28 |
| D | Pitch accuracy | 5 | 36 |
| E | Anti-slop hard-blocks | 5 | 0 (binary veto) |

---

## Category A — Voice fidelity (5 criteria, 35 pts)

Validates against the brand voice doc in `docs/02-brand/`. Populate banned-word lists from that doc — the lists below are generic defaults.

| # | Criterion | Description | Weight | Test method | Scoring |
|---|---|---|---|---|---|
| A1 | Credibility (no buzzwords) | Specific + precise. No "innovative," "game-changing," "revolutionary," "world-class," "seamless," "effortless," "next-generation." Uses the domain's actual terms. | 9 | Regex grep against the banned-list in `docs/02-brand/`. Any match = 0. Zero matches = 9. | Fail on any buzzword. |
| A2 | Practitioner-first tone (not executive) | Opens with the lead's working problem, not an executive summary. No "empower," "transform," "unlock," "leverage," "synergy," "paradigm," "holistic." | 8 | Semantic: do the first 2 sentences jump into a lead-specific problem, or start with "we help enterprises" / "our solution enables"? | 0–8. Executive-first opener = 0. |
| A3 | Honest confidence (no absolutes) | Acknowledges tradeoffs. No "zero overhead," "never fails," "instantly solves." Prefers a qualified, numbered claim over a superlative. No scare tactics. | 8 | Semantic: absolute claim = 0. Qualified claim with numbers = 8. | 0–8. |
| A4 | Plainly clear (short sentences + paragraphs) | Paragraphs 1–3 sentences. No walls of text. Acronyms defined on first use. Simple sentence structure. | 5 | Count sentences per paragraph. Any >4 = 0. All ≤4 = 5. Verify acronym definitions. | 0–5. |
| A5 | Urgency without fear-mongering | Genuine business urgency (funding, hiring, audit, launch). Not "your business is at risk," "catastrophic," "ticking time bomb." | 5 | Semantic: real urgency cue = 5. Generic = 2. Scare tactics = 0. | 0–5. |

**Subtotal:** 35 max.

---

## Category B — Specificity & personalization (5 criteria, 35 pts)

Every personalization token must trace to an enrichment field. Hallucinated personalization = hard fail.

| # | Criterion | Description | Weight | Test method | Scoring |
|---|---|---|---|---|---|
| B1 | Lead name + title accuracy | Addresses lead by first name + correct title. Must match `lead_title` from enrichment or public LinkedIn. | 5 | Cross-check `{{first_name}}` + `{{contact_title}}` against enrichment. Both correct = 5. Name only = 2. Both wrong = 0. | 0–5. |
| B2 | Company-specific signal | References a specific, verifiable fact: recent funding (amount + date), launch, hiring, documented requirement, documented stack. | 10 | For each personalization claim: trace to an enrichment field. All trace = 10. Partial = 5. **Any hallucinated claim = 0 + hard fail.** | Fail on hallucination. Else 0–10. |
| B3 | Relevant pain-point reference | Specific pain from enrichment, NOT generic ("you're growing fast"). *(Generic example: "ACME AI's job post mentions manual dispatch bottlenecks" — traceable; "you probably struggle with scale" — generic.)* | 8 | Check `enrichment.pain_points` + discovery for the pain mentioned. Traceable specific = 8. Generic = 2. Hallucinated = 0. | 0–8. |
| B4 | Stack/vendor accuracy | All product/vendor references match `enrichment.tech_stack`. If the email says "switching from Vendor X," the stack must contain Vendor X. | 7 | Cross-check every vendor name against enrichment. All match = 7. Any mismatch = 0. | 0–7. |
| B5 | No hallucinated personalization | Does NOT claim facts not in enrichment ("I saw your blog post about X" when no blog exists; "you work with [customer]" when no relationship is documented). | 5 | Read draft for personalization claims. Any unverifiable claim = hard fail. | Fail on hallucination. Else pass (5). |

**Subtotal:** 35 max.

---

## Category C — Value clarity & proportionality (4 criteria, 28 pts)

One clear ask. Fits the engagement stage.

| # | Criterion | Description | Weight | Test method | Scoring |
|---|---|---|---|---|---|
| C1 | Single clear ask | ONE primary ask: short call, one resource, one question. NOT three competing asks. | 10 | Count CTAs/value props. 1 = 10. 2 = 5. 3+ = 0. | 0–10. |
| C2 | Ask proportional to engagement stage | Cold = light ask (read, short call). Warm intro = medium. Evaluation-stage = heavier. | 9 | Determine stage from enrichment. Cold + heavy ask = 0. Cold + light ask = 9. | 0–9. |
| C3 | Value prop clarity | Articulates what the product does *for this lead's situation*, in one plain sentence. Not vague, not a feature list. | 6 | Semantic: can the lead understand from the email what you solve for them? Clear + specific = 6. Vague = 2. Absent = 0. | 0–6. |
| C4 | Social proof / anchor (bonus) | References a public customer, benchmark, or analyst mention from the vetted-claims list — only if authentic to the lead's segment. | 2 | Cited + relevant = 2. Cited but irrelevant (overstatement) = −2. Absent = 0. | −2 to 2. |

**Subtotal:** 28 max.

---

## Category D — Pitch accuracy (5 criteria, 36 pts)

Positioning per `docs/01-market-intelligence/` + `docs/04-marketing/content-ops/claims-vetted.md`. No drift.

| # | Criterion | Description | Weight | Test method | Scoring |
|---|---|---|---|---|---|
| D1 | Positioning alignment | Product description aligns with 1+ of the positioning pillars defined in `docs/01-market-intelligence/`, and the *right* pillar for the lead's segment. | 9 | Check text against the positioning doc's segment → pillar mapping. Accurate = 9. Conflated = 3. Wrong = 0. | 0–9. |
| D2 | Claims traceable to vetted list | Every claim about the product appears in `docs/04-marketing/content-ops/claims-vetted.md`. Unvetted claims must be wrapped `> CLAIM TO VERIFY:` or the draft fails. | 9 | Match each claim against the vetted list. Vetted = 9. Unvetted + no wrapper = 0 (fail + rewrite). | Fail on unvetted unwrapped claim. |
| D3 | No unsupported quantitative claims | Any specific metric requires a citation in the vetted-claims list. A specific number without a source = fail; a general qualitative statement is acceptable. | 8 | Grep for numbers. Each: cited? Yes = 8. Specific number without source = 0. No numbers = 8. | 0–8. |
| D4 | No competitive trash-talk | Competitor mentions must be factual and cite the competitor's own public sources. No character assassination. Honest, sourced comparison is OK. | 7 | If a competitor is mentioned: cited + factual = 7. Unverified = 0. No mention = 7 (N/A). | 0–7. |
| D5 | Pricing / roadmap absent | Does NOT mention pricing, commercial terms, or unshipped/beta/roadmap features. Only released capabilities. | 5 | Check for pricing / "coming soon" / "roadmap" / "beta." Found unwrapped = 0. Absent or wrapped = 5. | Fail on unwrapped pricing/roadmap. |

**Subtotal:** 36 max.

---

## Category E — Anti-slop (5 hard-blocks, 0 pts)

Binary. **ONE hit = fail, regardless of overall score.**

| # | Hard-block | Description | Test method | Trigger |
|---|---|---|---|---|
| E1 | Banned opening phrases | Does NOT open with "hope this finds you well," "circling back," "just checking in," "in today's [X] landscape," "it's no secret that," "whether you're X or Y," "the world of," "have you ever wondered," or a question mark. | Regex match on first 1–2 sentences (case-insensitive). | Any hit = fail. |
| E2 | No generic stock phrases | Does NOT use "reach out to discuss," "I'd love to connect," "let's explore together," "at your convenience," "looking forward to hearing from you." | Semantic check on closing lines. | Fail on templated close. |
| E3 | No punctuation abuse | ≤2 em-dashes total. No "..." ellipses unless essential. No ALL CAPS. ≤2 exclamation marks. | Count em-dashes, ellipses, exclamations, CAPS. | Fail over threshold. |
| E4 | Mobile-readable | No paragraph over ~80 words when reflowed on mobile. No walls of text. | Any paragraph >100 words unbroken = fail. | Fail on wall. |
| E5 | No jargon without context | Every non-standard acronym defined on first use (except universally known ones like CEO/CTO/AI). Domain-specific terms explained if not in the lead's own enrichment context. | For each acronym: defined within 2 sentences of first use? | Fail on undefined jargon. |

**Category E:** Pass = zero hits. Fail = any single hit → return to generator with feedback.

---

## Scoring calculation

**Total available:** 134 points (A: 35 + B: 35 + C: 28 + D: 36; E is a binary veto-gate)

**Normalization:** `final_score = (A + B + C + D) / 134 × 100`

**Pass threshold:** normalized score ≥ `icp.qualification_thresholds.copy_pass` AND all Category E pass.

---

## Workflow

1. Load draft from generator. Parse subject, body, CTA, links, personalization tokens. Identify engagement stage from enrichment.
2. Run **Category E hard-blocks first.** Any trigger → immediate fail + feedback: "Hard-block [E1–E5] triggered: [specific reason]. Rewrite." Do not score A–D.
3. Score A–D. Log each criterion.
4. Calculate normalized score.
5. Decision:
   - ≥ `copy_pass` AND E pass: **PASS** → send queue (still gated on human approval). Log.
   - < `copy_pass` OR E fail: **FAIL** → return to generator with feedback. Increment retry counter.
   - Retry ≥5: **ESCALATE** → human reviewer with draft + full scoring log + all attempts.

## Output schema

```json
{
  "draft_id": "seq-123-example-prospect",
  "lead_email": "sam@example-prospect.com",
  "decision": "PASS | FAIL | ESCALATE",
  "normalized_score": 82.1,
  "category_scores": { "A": 32, "B": 33, "C": 26, "D": 34 },
  "failing_criteria": ["B3_pain_point_hallucinated", "C1_multiple_asks"],
  "hard_block_hits": [],
  "retry_count": 0,
  "feedback": "Lead with the documented pain from enrichment, not the generic opener. Single CTA.",
  "timestamp": "ISO-8601"
}
```

---

## Notes for the evaluator LLM

- **The personalization audit is strict.** If a claim cannot be traced to the enrichment JSON, it's hallucinated. Hallucinated personalization is a hard fail — the worst possible outcome, because it kills the relationship if caught.
- **Hard blocks are non-negotiable.** One banned phrase, one unverifiable claim, one generic close = fail. These are the slop markers that make cold email feel like spam.
- **Category D is pitch integrity.** Every product claim must be in `claims-vetted.md` or the draft fails.
- **Specificity (Category B) beats cleverness.** Generic-but-safe = low B score. Personalization must be traceable and relevant.
- **Mobile readability is non-negotiable** for cold email — enforce E4 aggressively.

## Integration with sequence-enrollment

- Generator input: lead enrichment JSON + sequence template (from `../sequences/`)
- Evaluator reads draft + enrichment; runs A–E, scores, decides
- Feedback on fail: structured error codes (e.g., `A1: buzzword at line 5`, `B2: hallucinated claim`, `E1: banned opening`) + a suggested rewrite angle
- Passing drafts enter the human-approval queue with tracking metadata

## Maintenance

The monthly feedback-loop agent proposes edits based on human edits to approval PRs. Threshold changes go in `company-profile.yaml`. Structural changes require a decision-log entry.
