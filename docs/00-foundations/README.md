---
title: Foundations
description: The two field-notes papers that motivate this template. Read these before running `/gtm-init`.
owner: charlcye
status: approved
last_reviewed: 2026-08-25
---

# Foundations

The two papers in this folder describe the framework this template implements. Read them before running `/gtm-init` if you want to understand why the repo is shaped the way it is — the numbered folder taxonomy, the frontmatter discipline, the rubric-gated loops, the earned-autonomy ladder — instead of just accepting them.

| Paper | What it is |
|---|---|
| [Context, Loops, Graphs](./context-loops-graphs.md) | The framework paper. Three levels: a single source of truth, at least one production loop, and a self-improving coding harness. Each level pays for itself; skipping ahead produces confident garbage. |
| [The Coding Harness](./the-coding-harness.md) | The implementation companion. Phase-by-phase build order from L1-0 through L3-6, with the workflows, hooks, guardrails, and readiness gates named. This template ships the L1 and L2 skeletons; the paper covers all three levels end to end. |

## How this template maps to the papers

- **Level 1 (SSOT)** — the `docs/` tree in this repo. The numbered domain folders, `company-profile.yaml`, and `CLAUDE.md` correspond to the L1-0 and L1-1 phases in *The Coding Harness*.
- **Level 2 (loops)** — the `agents/` pipeline plus the content-ops workflows in `.github/workflows/`. Corresponds to L2-0 through L2-2.
- **Level 3 (coding harness)** — not shipped as live scaffold in this template. See the skeleton under [`../../examples/agent-ops-skeleton/`](../../examples/agent-ops-skeleton/) for the concrete shape; build your own `agent-ops` repo from it when the L2 loop is running steadily.

The papers are the "why." This template is the "here's one." Adapt liberally.

## Now open a skeleton

After the papers land, go read one of the reference skeletons under
[`../../examples/`](../../examples/):

- **Level 2 mature reference** — [`../../examples/sales-ops-skeleton/`](../../examples/sales-ops-skeleton/): the full outbound loop with 23 workflows, kill switch, EU router, deliverability monitor, judge-evals regression harness. Fuller than the template's own `../../agents/` live scaffold.
- **Level 3 reference** — [`../../examples/agent-ops-skeleton/`](../../examples/agent-ops-skeleton/): the coding harness end to end — ticket intake, spec-drafter, implementer, two fresh-context reviewers, code-judge, autonomy ledger, dream loop, release intelligence.

[`../../examples/README.md`](../../examples/README.md) has a phase-to-file lookup that maps every L2-* and L3-* phase in *The Coding Harness* to the specific workflow, agent prompt, or lib file that implements it. Useful when you want to jump straight to "what does L3-2's implement.yml look like?"
