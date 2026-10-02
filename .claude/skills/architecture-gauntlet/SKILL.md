---
name: architecture-gauntlet
description: Run a structured, adversarial design exercise on a new or proposed architecture — constraints first, three options ranked from most to least boring, a hostile principal-engineer review and an 18-month premortem run by fresh-context subagents, then risk mitigations, tripwires, an ADR and a diagram. Use this whenever someone is ideating, choosing, or stress-testing a system design — "how should we architect X", "is this design sound", "poke holes in this architecture", "premortem this", "which approach for our new service", "we're thinking about moving to Y", a design doc or RFC to pressure-test, or any build-vs-choose infrastructure decision — even if they never say "architecture" or "gauntlet". Prefer this over just answering with a recommended stack.
---

# Architecture Gauntlet

A repeatable exercise that turns "Claude, design my system" into a decision the human owns, with its risks surfaced and mitigated before code is written.

## Why this shape

LLMs are agreeable and pattern-complete toward the default stack. Asked to design, they produce a confident, pretty, median architecture; asked to review their own design in the same context, they defend it. The exercise counters both:

- **Constraints before solutions.** The design space is set by team size, on-call appetite, budget, deploy cadence, and past failures, not by what's fashionable. Constraints collected after options get bent to fit the favorite.
- **Forced alternatives, ranked by boringness.** Boring is a feature: known failure modes, hireable skills, existing runbooks. Novelty must earn its place against a boring baseline.
- **The human picks.** Claude scores and explains; the human decides. Claude's opinion comes *after* the pick so it can't anchor.
- **Split contexts.** The reviewer and premortem panel are fresh subagents who see only a written brief. They weren't in the room when the design was sold, so they can't be charmed by it. One giant "design everything" conversation is how you get the default architecture.
- **Critique without fixes.** Reviewers that must propose fixes soften their critique to what they can fix. Separate finding problems from solving them.

## The phases

Work through these in order. Each phase ends at a checkpoint where the human confirms or corrects before you go on — the checkpoints are the point, not overhead. Keep each checkpoint message tight: the artifact, then one clear question.

Create a working folder at the start: inside a git repo, `docs/architecture/<slug>/`; otherwise `./architecture-gauntlet/<slug>/`. Everything the phases produce is written there, which is also what lets subagents see the brief without the conversation.

### Phase 0 — Frame the decision

Restate the request as a *decision*, not a design task. "What architecture should we use for search?" becomes "Choose how query-time filtering is executed for tenant-isolated search at 10× current volume, given X." A good frame names what's being decided, what's out of scope, and the time horizon (default 18 months).

If you're in a codebase, read enough to ground the frame: existing ADRs (look for folders like `docs/adr`, `adr/`, `decisions/`, `architecture-decisions/`, and any ADR template there), the README, the deploy config, the component the decision touches. Cite what you found. Don't ask the human for facts the repo already answers.

### Phase 1 — Constraint dump

Ask the human to dump constraints, with no solution question attached. Offer the checklist in `assets/brief-template.md` (team & skills, on-call appetite, budget, scale now/18mo, latency/SLOs, compliance & data residency, security model, deploy cadence, existing stack & sunk cost, the last production failure, hard deadlines, what must not change). Accept a messy paragraph; you do the structuring.

Then **cross-check the constraints against each other and against the repo** before moving on. Look for contradictions ("Anthropic API only" vs. "no US data transfer"), constraints that are secretly preferences, and unstated ones implied by the context (a regulated customer implies audit logging). Present these as a short list: *contradictions*, *probably-preferences*, *implied constraints I added*. Resolve contradictions with the human; an unresolved contradiction poisons every later phase.

Write `brief.md` from the template. **Checkpoint:** "Is this brief right? Anything missing or wrong?"

### Phase 2 — Assumptions ledger

List the assumptions the brief rests on (about load, user behavior, team capacity, vendor behavior, the threat model, cost curves). For each: the failure mode if it's wrong, a risk rank (likelihood × blast radius), and an evidence tag:

- **Measured** — there's data
- **Observed** — anecdote or early signal
- **Assumed** — plausible, unverified
- **Hoped** — load-bearing and nobody's checked

Cheap-to-verify, high-rank assumptions get a concrete verification step ("run the benchmark on the 50M-vector shard", "ask the customer whether they need per-tenant keys"). Append to `brief.md`. Short checkpoint — the human can skip ahead.

### Phase 3 — Three options, most boring to least boring

Generate three genuinely different architectures — different in approach, not in vendor. Order them:

1. **Boring** — the most conventional thing that meets the constraints; heavy use of what the team already runs.
2. **Middle** — one deliberate departure from the boring path, justified by a specific constraint.
3. **Novel** — the least boring option that's still defensible, the one that bets on something.

If the novel option can't be justified by a constraint, say so. That's a finding, not a failure.

For each option: a 3–5 sentence sketch plus a small Mermaid diagram if it helps, **cost** (build + run, rough USD), **ops burden** (who gets paged for what), **when it breaks** (the specific load or condition), **18-month failure mode** (the most likely story of how it ends up being rewritten), and **reversibility** (how expensive it is to back out).

Then a scoring matrix: options × the brief's top constraints, each cell a short phrase, not a number — numbers invite fake precision. Write to `options.md`.

**Do not recommend at this stage.** **Checkpoint:** "Which one are you taking into review, and why?" Record the human's reason verbatim; it becomes the ADR rationale. *After* they pick, give your view in two or three sentences — agree, or name the specific constraint you think points elsewhere. If the human asks for your pick before choosing, give it with the reasoning, but note that you're anchoring them.

### Phase 4 — Hostile review and premortem (parallel, fresh context)

Write `chosen.md`: the brief, the assumptions ledger, and the chosen option's full description. Leave out the rejected options and the conversation. Then spawn these subagents **in the same turn**, each given only the path to `chosen.md` and its prompt from `references/subagent-prompts.md`:

- **Hostile reviewer** (1 agent): a principal engineer who has shipped two failed systems. Lists why this design will fail. No fixes.
- **Premortem panel** (3 agents, one lens each): "It's 18 months later and this system is being rewritten. Write the postmortem." Lenses: *Operator & on-call* / *Customer & adversary* (includes security and abuse) / *Future maintainer & the business* (includes cost, hiring, vendor, org changes).

Why separate agents instead of one: each lens produces its most specific failure only when it isn't competing for attention with the others, and duplicated findings across independent agents are a signal.

If subagents aren't available (e.g., claude.ai), tell the human that the independence is weaker, then run each role sequentially, re-reading only `chosen.md` before each and writing each result to its own file before starting the next.

### Phase 5 — Consolidate and mitigate

Merge the four outputs into a risk register (`risks.md`). Deduplicate, noting how many independent agents raised each risk. Rank by likelihood × blast radius, and flag anything raised by 2+ agents or tied to a **Hoped** assumption. Discard items that are generic ("could have bugs") or already handled by a stated constraint, and say that you discarded them.

For each of the top risks (typically 5–8), present 2–3 mitigation directions with trade-offs, and let the human pick. Expand each pick into:

- **Prevent** — the design change that makes the failure less likely
- **Detect** — the signal that tells you it's happening (metric, alert, review cadence)
- **Tripwire** — the concrete threshold at which you change course
- **Limit damage** — what to do when it happens anyway
- **Owner** (a role, not a name) + **first step**

Some risks should change the design itself rather than be mitigated around it. When the chosen option needs a structural change, say so plainly and update `chosen.md`. If the right answer is a different option, go back to Phase 3 with the human.

### Phase 6 — Decide

Make the decision-forcing statement explicit:

- **Decision:** what we're building, in one sentence
- **Why the others lost:** one line each, in terms of the brief's constraints
- **Tripwires:** the conditions that would force a mid-flight change (collected from Phase 5)
- **Contingency:** the fallback if a tripwire fires, usually the boring option, plus what we'd have to have kept reversible to make it viable
- **Open questions** that block commitment, each with an owner and how to close it

Then give an overall call: **proceed**, **proceed with reduced scope**, **spike first** (name the spike and what result would change the call), or **don't build**. For anything other than proceed, run a quick **reverse premortem**: "18 months from now, we regret *not* building this. Why?" Premortems are biased toward caution, and this corrects for that.

### Phase 7 — Artifacts

Produce, in the working folder:

1. **`ADR.md`** — match the repo's existing ADR format and numbering if one exists; otherwise use `assets/adr-template.md`. It includes the context (from the brief), the decision, the options considered, the consequences, the risks & mitigations table, tripwires, and the contingency.
2. **Diagram** — the chosen architecture. If the `archify` skill is available, use it for a polished HTML diagram; otherwise write a Mermaid C4-style container diagram into the ADR. Draw only the chosen option. Diagrams of rejected options make them look more alive than they are.
3. **`risks.md`** — the register from Phase 5, updated with the picks.

Finish with a short summary in chat: the decision, the top three risks with their tripwires, the open questions, and the file paths. Offer to turn the first steps into tickets, but don't file them unasked.

## Running a lighter pass

When the human wants speed ("quick gauntlet", "just premortem this", a small or reversible decision), compress: take constraints from whatever they gave, skip the assumptions checkpoint, run only the hostile reviewer and one premortem agent, and produce a risk list plus tripwires instead of a full ADR. Say which phases you skipped. When the human brings an existing design doc, start at Phase 1: extract constraints from the doc and check them for contradictions, then go to Phase 4 with the doc as the chosen option. Offer Phase 3 alternatives only if review shows the design is shaky.

## Things that go wrong

- **Sliding into recommending early.** If you catch yourself writing "I'd suggest option 2" before the human picks, delete it.
- **Options that differ only by vendor.** Postgres vs. MySQL is not an architectural alternative. Vary the approach: sync vs. async, centralized vs. per-tenant, buy vs. build, fewer moving parts vs. more.
- **Leaking the conversation into subagents.** Pass the file path, not a summary written in your voice. Your summary carries your enthusiasm.
- **Soft critique.** If a reviewer's output is mostly hedges or mostly fixes, re-run it with the prompt's "no fixes, no hedging" constraint restated.
- **Treating the risk register as the deliverable.** The deliverable is a decision with tripwires. A long unranked risk list is decision drag.
