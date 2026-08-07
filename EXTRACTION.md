# Extraction Checklist

Source systems: `cyborginc/cyborgdb-internal-docs` (docs SSOT + content ops, 23 workflows) and `cyborginc/sales-ops` (15 pipeline agents). This file tracks what was ported, how, and what must never enter this template. Port completed 2026-08-07; statuses below. Anything marked "needs live test" has not yet run on a real instance with secrets set.

Legend — **GENERIC**: copied + genericized. **CONFIG**: ported, hardcoded values replaced with `company-profile.yaml` reads. **DROP**: Cyborg-specific, not ported.

## From internal-docs

| Component | Source path | Class | Status |
|---|---|---|---|
| 8-domain SSOT structure + per-domain CLAUDE.md | repo root | GENERIC | done (6 domains; eng-docs + team-culture dropped as non-GTM) |
| Positioning architecture / messaging framework | `01-market-intelligence/` | CONFIG | skeleton + drafted per-instance by /gtm-init |
| ICP + filter criteria YAML | `01-*/ideal-customer-profile.mdx`, `03-*/icp-filter-criteria.yaml` | CONFIG | done — folded into company-profile.yaml; reasoning doc per-instance via /gtm-init |
| Buyer personas playbook | `01-market-intelligence/buyer-personas/` | CONFIG | per-instance via /gtm-init |
| Competitive landscape | `01-market-intelligence/competitive-landscape/` | CONFIG | per-instance via /gtm-init |
| Brand voice + voice-eval rubric v2 | `02-brand/` | CONFIG | voice doc per-instance via /gtm-init; voice dimensions live inside copy-evaluator rubric (no separate voice-eval rubric ported) |
| Sales playbook + objection handling | `03-commercial-revenue/sales-playbook*` | CONFIG | done — generic skeleton |
| Sequences (4-touch + 21d nurture) | `03-commercial-revenue/sequences/` | CONFIG | done — shells, zero product claims, claims-vetted gate |
| Rubrics (pre-seed qualifier, qualifier-critic, copy-evaluator) | `03-commercial-revenue/rubrics/` | CONFIG | done — thresholds read from config; **golden-set eval fixtures still todo** |
| Pricing architecture | `03-commercial-revenue/pricing-architecture.mdx` | DROP | done — empty skeleton + decision-log rule shipped |
| Account context system | `03-commercial-revenue/accounts/` | GENERIC structure, DROP content | done — redacted example-account |
| Content-ops pipeline + runbook | `04-marketing/content-ops/` | CONFIG | done — genericized runbook + reference templates |
| claims-vetted.md | `04-*/content-ops/reference/` | DROP content | done — empty table + instructions at `docs/04-marketing/content-ops/claims-vetted.md` |
| Launch playbook | `04-marketing/launch-playbook.md` | GENERIC | done |
| Decision log + ADR convention | `06-operational/decision-log/` | GENERIC | done — README + TEMPLATE |
| Agent provenance | `06-operational/agent-provenance.md` | GENERIC | done (trailer convention); **enforcement hooks (.claude/hooks/) still todo** |
| Frontmatter schema + doc-index rules | `.claude/rules/` | GENERIC | done |
| Workflows: competitor-refresh, aeo-monitoring, aeo-gap-remediation, blog-auto-draft, weekly-digest, health-map, pr-comment-resolver, weekly-engineering-signals (+ exemplar weekly-competitive-signals) | `.github/workflows/` | CONFIG | done — stage gates + missing-secret skips; needs live test. aeo-monitoring, cve-monitor, health-map, weekly-digest, engineering-signals are simplified reimplementations (source versions were entangled with Cyborg infra: state branches, headless-browser stack, site-repo PATs) |
| Workflows: cve-monitor, regulatory-monitor, conference-tracker, analyst-signals, product-market-updates | `.github/workflows/` | CONFIG — vertical-dependent | done — ported dormant (cron commented, dispatch-only) |
| Workflows: granola-meeting-sync, attio-call-sync, claude-updates-digest, deploy, blog-publisher, blog-hero-image-autogen, pr-merged-dispatcher, docs-drift-review | `.github/workflows/` | DROP (tool/site-specific); docs-drift-review optional series-a port later | — |
| CyborgFHE parallel-product pattern | `*/cyborgfhe/` | GENERIC pattern, DROP content | done — documented in `docs/05-product/CLAUDE.md` |

## From sales-ops

| Component | Source path | Class | Status |
|---|---|---|---|
| Crawler | `agents/crawler/` | CONFIG | done — Apollo optional; needs live test |
| Event ingest | `agents/event-ingest/` | CONFIG | done — needs live test |
| Dedup | `agents/dedup/` | GENERIC | done — via CRM adapter |
| Pre-filter | `agents/pre-filter/` | CONFIG | done |
| Enrichment | `agents/enrichment/` | CONFIG | done — Apollo/Hunter/Exa all optional |
| Stack-profile | `agents/stack-profile/` | GENERIC | done |
| Qualifier-critic | `agents/qualifier-critic/` | CONFIG | done — rubric read locally (cross-repo PAT removed); retired E5 slot dropped |
| Sequence enrollment + PR approval flow | `agents/sequence-enrollment/` | CONFIG | done — needs live test |
| Copy-evaluator | `agents/copy-evaluator/` | CONFIG | done — grounds on local claims-vetted + voice docs |
| Feedback loop | `agents/feedback-loop/` | GENERIC | done |
| SMTP send + suppression + EU router | `lib/smtp_send.py`, `lib/suppression.py`, `lib/eu_router.py` | GENERIC | done — provider/cap/window from config |
| CRM adapter | `lib/attio.py` | CONFIG | done — `lib/crm.py` with attio / airtable / none (local JSONL) backends; airtable + none backends need live test |
| Exa search wrapper | `lib/exa_search.py` | GENERIC | done |
| Deliverability monitor | `deliverability-monitor.yml` | GENERIC | done |
| Warmup | `warmup.yml` | CONFIG | done — ramp/caps from config |
| Reply monitor | `reply-monitor.yml`, `lib/imap_poll.py` | CONFIG | done — mailbox via IMAP_* secrets, notifications via channels config (hardcoded people/mailbox removed) |
| Evergreen nurture | `agents/evergreen-nurture/` | CONFIG | done — de-Attio'd via CRM adapter |
| Pipeline heartbeat | `pipeline-heartbeat.yml` | GENERIC | done |
| Golden-set evals | `judge-evals` | CONFIG | **todo — fixtures must be re-seeded generically** |

## Remaining work

1. Golden-set eval fixtures for the three rubrics (generic, fictional-company based)
2. Provenance enforcement hooks (`.claude/hooks/`)
3. Live end-to-end test on a real instance with secrets set (see SECRETS.md)
4. Optional series-a port: docs-drift-review

## NEVER port (confidentiality)

- Any file under sales-ops `leads/` or `sends/` (named prospects, event batches, outreach drafts)
- `accounts/` content, call notes, roadmap responses
- Pricing numbers, claims-vetted content, retired-claims lists
- Hardcoded people (notification DMs, sender identities), mailboxes, or Cyborg domains
- Cross-repo PATs / secret values of any kind
