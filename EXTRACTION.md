# Extraction Checklist

Source systems: `cyborginc/cyborgdb-internal-docs` (docs SSOT + content ops, 23 workflows) and `cyborginc/sales-ops` (15 pipeline agents). This file tracks what gets ported, how, and what must never enter this template.

Legend — **GENERIC**: copy + genericize wording. **CONFIG**: port, replace hardcoded values with `company-profile.yaml` reads. **DROP**: Cyborg-specific, do not port.

## From internal-docs

| Component | Source path | Class | Status |
|---|---|---|---|
| 8-domain SSOT structure + per-domain CLAUDE.md | repo root | GENERIC | scaffolded (6 domains; eng-docs + team-culture dropped as non-GTM) |
| Positioning architecture / messaging framework | `01-market-intelligence/` | CONFIG | skeleton |
| ICP + filter criteria YAML | `01-*/ideal-customer-profile.mdx`, `03-*/icp-filter-criteria.yaml` | CONFIG | folded into company-profile.yaml |
| Buyer personas playbook | `01-market-intelligence/buyer-personas/` | CONFIG | todo |
| Competitive landscape | `01-market-intelligence/competitive-landscape/` | CONFIG | todo |
| Brand voice + voice-eval rubric v2 | `02-brand/` | CONFIG | skeleton |
| Sales playbook + objection handling | `03-commercial-revenue/sales-playbook*` | CONFIG | todo |
| Sequences (4-touch + 21d nurture) | `03-commercial-revenue/sequences/` | CONFIG — strip all product claims | todo |
| Rubrics (pre-seed qualifier, qualifier-critic, copy-evaluator) | `03-commercial-revenue/rubrics/` | CONFIG — re-seed golden sets | todo |
| Pricing architecture | `03-commercial-revenue/pricing-architecture.mdx` | DROP — ship empty skeleton + decision-log rule | skeleton |
| Account context system | `03-commercial-revenue/accounts/` | GENERIC structure, DROP content — ship 1 redacted example | skeleton |
| Content-ops pipeline + runbook | `04-marketing/content-ops/` | CONFIG | todo |
| claims-vetted.md | `04-*/content-ops/reference/` | DROP — ship empty template with instructions | todo |
| Launch playbook (generic half of PR #312 split) | `04-marketing/launch-playbook.md` | GENERIC | todo |
| Decision log + ADR convention | `06-operational/decision-log/` | GENERIC | skeleton |
| Agent provenance + team-memory hooks | `06-*/agent-provenance.md`, `.claude/hooks/` | GENERIC | todo |
| Frontmatter schema + doc-index rules | `.claude/rules/` | GENERIC | todo |
| Workflows: competitive-signals, competitor-refresh, aeo-monitoring, aeo-gap-remediation, blog-auto-draft, weekly-digest, health-map, pr-comment-resolver | `.github/workflows/` | CONFIG | exemplar ported (competitive-signals) |
| Workflows: cve-monitor, regulatory-monitor, conference-tracker, analyst-signals | `.github/workflows/` | CONFIG — vertical-dependent, off by default | todo |
| Workflows: granola-meeting-sync, attio-call-sync, claude-updates-digest, deploy, docs-drift-review | `.github/workflows/` | DROP (tool-specific / Cyborg-specific); docs-drift-review optional series-a port | — |
| CyborgFHE parallel-product pattern | `*/cyborgfhe/` | GENERIC pattern, DROP content — document in 05-product | todo |

## From sales-ops

| Component | Source path | Class | Status |
|---|---|---|---|
| Crawler | `agents/crawler/` | CONFIG (Apollo key optional) | todo |
| Event ingest | `agents/event-ingest/` | CONFIG | todo |
| Dedup | `agents/dedup/` | GENERIC (via CRM adapter) | todo |
| Pre-filter | `agents/pre-filter/` | CONFIG | todo |
| Enrichment | `agents/enrichment/` | CONFIG (Apollo/Hunter/Exa optional) | todo |
| Stack-profile | `agents/stack-profile/` | GENERIC | todo |
| Qualifier-critic | `agents/qualifier-critic/` | CONFIG (rubric local, not cross-repo) | todo |
| Sequence enrollment + PR approval flow | `agents/sequence-enrollment/` | CONFIG | todo |
| Copy-evaluator | `agents/copy-evaluator/` | CONFIG | todo |
| Feedback loop | `agents/feedback-loop/` | GENERIC | todo |
| SMTP send + suppression + EU router | `lib/smtp_send.py`, `lib/suppression.py`, `lib/eu_router.py` | GENERIC | todo |
| CRM adapter | `lib/attio.py` | CONFIG — abstract to attio/airtable/none | todo |
| Exa search wrapper | `lib/exa_search.py` | GENERIC | todo |
| Deliverability monitor | `deliverability-monitor.yml` | GENERIC | todo |
| Warmup | `warmup.yml` | CONFIG | todo |
| Reply monitor | `reply-monitor.yml`, `lib/imap_poll.py` | CONFIG — parameterize mailbox + notification targets (currently hardcoded) | todo |
| Evergreen nurture | `agents/evergreen-nurture/` | CONFIG — de-Attio via CRM adapter | todo |

## NEVER port (confidentiality)

- Any file under sales-ops `leads/` (named prospects, event batches, outreach drafts)
- `accounts/` content, call notes, roadmap responses
- Pricing numbers, claims-vetted content, retired-claims lists
- Hardcoded people (notification DMs, sender identities), mailboxes, or Cyborg domains
- Cross-repo PATs / secret values of any kind
