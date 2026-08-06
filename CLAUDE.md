# Startup Intel Stack — Agent Instructions

This repo is a company's GTM single source of truth plus the agents that operate on it. Read `company-profile.yaml` first — it holds every company-specific parameter. Do not hardcode company names, people, domains, thresholds, or schedules anywhere else.

## Universal rules

1. **SSOT discipline.** Docs in `docs/` are canonical. Agents ground every claim in these docs; if a needed doc is missing or stale, flag it — don't improvise facts about the company.
2. **Config over constants.** Any value that would differ for another company belongs in `company-profile.yaml`.
3. **Stage gating.** Check `company.stage` before running; skip work above the current tier (see README).
4. **CI, not laptops.** Recurring automation runs on GitHub Actions in this repo. Explicit least-privilege `permissions:` block in every workflow.
5. **Human approval gates.** No outbound email without a merged approval PR. Never bypass rubric gates, suppression checks, `SEQUENCES_PAUSED`, or the daily send cap.
6. **Confidentiality.** Lead data (`leads/`) never leaves this repo. No named prospects in docs, issues, or anything shared.
7. **Decision log.** Load-bearing changes (positioning, pricing, ICP, strategy) require a dated entry in `docs/06-operational/decision-log/`.
8. **Frontmatter.** Every doc in `docs/` carries YAML frontmatter: `title`, `description`, `owner`, `status`, `last_reviewed`.
9. **Provenance.** CI agents add commit trailers: `Agent:`, `Agent-Model:`, `Triggered-By:`.

## Layout

- `docs/01-market-intelligence/` — positioning, messaging, ICP, personas, competitors
- `docs/02-brand/` — voice, tone, visual identity, voice-eval rubric
- `docs/03-commercial-revenue/` — playbook, rubrics, sequences, pricing skeleton, accounts
- `docs/04-marketing/` — content ops, launch playbook, AEO
- `docs/05-product/` — roadmap, differentiators, parallel-product pattern
- `docs/06-operational/` — decision log, processes, glossary
- `agents/` — pipeline agent definitions (one folder per agent, CLAUDE.md each)
- `lib/` — shared Python: sending, suppression, CRM adapter, search
- `leads/` — pipeline data (gitignored patterns apply; private repo only)

## Onboarding

New instance? Run `/gtm-init`. It interviews the founder (or scrapes their website/LinkedIn/X), fills `company-profile.yaml`, drafts the `docs/` SSOT for correction, and opens the setup PR listing required secrets.
