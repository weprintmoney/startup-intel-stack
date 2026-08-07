---
title: "Agent Provenance Convention"
description: "How every agent-authored commit records which agent, model, and instruction revision produced it — commit-trailer spec for CI and interactive sessions."
owner: ""
status: template
last_reviewed: "2026-08-06"
---

# Agent Provenance Convention

Every commit authored by an agent must record **which agent, running which model, under which instruction revision, in which run** produced it — captured at commit time by the harness, not reconstructed afterward.

**Why this matters:** without trailers, a regression in agent-authored content traces to a commit, but not to the model or workflow revision that produced it. With them, a bad model upgrade or prompt change can be identified and rolled back as a unit, and "which artifacts did agent X touch" becomes a `git log --grep` query instead of forensics across expiring CI logs (~90-day retention on GitHub Actions).

---

## Trailer spec — CI agents

Commits from GitHub Actions workflows carry this trailer block (standard git trailers, appended after the commit body):

```text
Agent: <workflow-file-stem>
Agent-Model: <exact model id, e.g. claude-opus-4-7>
Agent-Harness: <harness@version (runner)>
Agent-Instructions: <path/to/instruction/source>@<short SHA>
Agent-Run: <full CI run URL>
Triggered-By: cron
```

| Trailer | Value | Why |
|---------|-------|-----|
| `Agent` | Agent slug = **workflow file stem** (e.g. `signals-monitor` for `signals-monitor.yml`) | Stable, registry-backed identity — not free text |
| `Agent-Model` | Exact model ID the agent invokes, never just the vendor name | Regressions trace to a model version |
| `Agent-Harness` | Harness + version, with runner in parens | The same prompt behaves differently across harness versions |
| `Agent-Instructions` | Path to the instruction source `@` the short SHA of the checkout the run executed from | Pins the exact prompt/workflow revision in effect |
| `Agent-Run` | Full CI run URL | The **verifiable bind** — server-generated evidence that can't be back-filled by hand |
| `Triggered-By` | `cron`, or `@handle (event)` for human-triggered runs | Distinguishes scheduled from human-initiated work |

Reviewer identity is **not** duplicated in trailers — PR approval already records it durably. A `Co-Authored-By` trailer may remain, but the `Agent-*` block is the canonical record.

## Trailer spec — interactive sessions

Commits made through interactive agent sessions in this repo carry a reduced block:

```text
Agent: interactive
Agent-Model: <model id of the session>
Triggered-By: @<GitHub handle of the human operating the session>
```

- `Agent-Run` and `Agent-Instructions` are omitted — there is no CI run URL, and the instruction context is the live session.
- Commits with no meaningful agent authorship (the human dictated the exact content) may skip the block.

## How workflows adopt it

Recommended mechanism: a shared step (composite action or setup script) that sets the bot git identity and installs a `prepare-commit-msg` hook in the job workspace, so **every** `git commit` in the job gets the trailer block automatically — no per-commit discipline required. Record provenance where it's true: the harness emits it during the run.

```yaml
- uses: ./.github/actions/agent-provenance   # or your equivalent
  with:
    agent: <workflow-file-stem>
    model: <model id>
```

Every committing workflow calls this before its first commit step. Enforce via review (or a hook) that no committing workflow ships without it.

## Querying provenance

```bash
git log --grep '^Agent: <slug>'        # everything one agent touched
git log --grep '^Agent-Model: <id>'    # everything a given model version produced
```

## Out of scope (deliberately, at early-stage team size)

- Queryable provenance database — `git log --grep` is sufficient
- Per-run trace storage — CI logs are the trace; trailers are the durable summary
- Cryptographic signing / attestations — revisit when a customer or auditor asks
