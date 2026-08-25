---
title: Context, Loops, Graphs
description: How a ten-person startup built its AI operating system from zero — the three-level framework this template implements.
owner: charlcye
status: approved
last_reviewed: 2026-08-25
---


# Context, Loops, Graphs

*How a ten-person startup built its AI operating system from zero.*

> **THE WHOLE PAPER IN FOUR LINES**
>
> 1. The project isn't "adopt AI." It's externalization — getting what your experts know out of their heads and into artifacts a machine can read and enforce.
> 2. Build in three levels: context, then loops, then graphs. Each one pays for itself. Skipping ahead produces confident garbage.
> 3. You almost certainly don't need new infrastructure. Git, CI, and pull requests carry Levels 1–3 further than anyone expects.
> 4. The human never leaves. They move up: from doing the work to owning the criteria that judge it.

---

## Who this is for

You run, or work at, a company of five to fifty people, and you suspect AI could be doing more for you than autocomplete and a chat window. This paper is the build order. I wrote it from inside a seed-stage infrastructure startup where we built this system level by level, and I've kept only what generalizes.

Read it as an executive deciding what to fund, or as the engineer who'll build it. There's a third option, and it's the one I'd actually recommend: hand this paper to your own Claude, point it at your repositories and your tools, and ask it to inventory your company against the checklists here and build the equivalent for your context. Every section ends with the artifacts required and a readiness gate, specifically so an agent can execute against it.

---

## Step 0 · The problem you actually have

At a small company, expertise is concentrated by design. One person owns positioning. One owns the core engine. One owns QA strategy. One owns the sales motion. That concentration is how specialized things get built — but it means every question, every review, every triage routes through the same few heads, and those heads spend most of their hours on work that wouldn't need their specific expertise if that expertise were written down somewhere a machine could read it.

Meanwhile, frontier models are already capable of a large share of that routed work. The bottleneck isn't model intelligence. The bottleneck is that your company's knowledge lives in people's heads, chat scrollback, meeting recordings nobody rewatches, and a wiki that was last accurate two reorgs ago. A model with no access to your truth produces confident, generic, wrong answers. The same model with organized access to your truth produces work you'd sign.

> So the project is not "adopt AI." The project is **externalization**: moving what your experts know out of their heads and into artifacts — documents, rubrics, checks, pipelines — that both humans and models can read, and that machines can enforce. Everything in this paper is a variation on that one move.

The other thing to know at step 0: don't attempt this as a big-bang transformation. The levels below build on each other, and each one produces value on its own. Teams that skip ahead build impressive demos that quietly produce garbage, because the layer underneath was never laid.

## The three-level model

| Level | What it is | What it unlocks | What it requires |
|---|---|---|---|
| **1 — Context management** | A single source of truth the AI can navigate, with automated checks keeping it accurate | Company Q&A from policies and playbooks; meeting notes with action items; dashboards and digests built from current information | An organized SSOT; hooks and rules that keep it clean; possibly a vector database at large corpus scale |
| **2 — Loops** | Draft → evaluate against explicit criteria → revise → repeat until it passes or escalates | Outbound that meets your messaging standards; support replies verified before a human sees them; code written until tests pass | A goal, the context from Level 1, and a checker — tests, a rubric, or a judge — so the loop knows when to stop |
| **3 — Graphs** | Several loops with explicit handoffs, shared run state, and approval branches | A self-improving coding harness; research → synthesize → write → independent fact-check; triage → specialist → human approval | Stateful orchestration — a framework like LangGraph, or (as you'll see) CI and git doing the same job |

Each level is a prerequisite for the next. That's not a purity rule; it's a description of what breaks when you skip.

---

## 1 · Simple context management

### What we built

A single repository — the company's single source of truth — organized into numbered domain folders: market intelligence, brand, commercial, marketing, product, operations, engineering, team culture. Git, not a wiki, and that choice is load-bearing: git gives you versioning, review before anything becomes "true," CI enforcement, and — critically — a medium agents can both read and write to through the same pull-request process humans use.

The pieces that made it work, in the order they mattered:

**Index briefs, not encyclopedias.** Every folder carries a short index file that says what lives here, what each document is for, and where to go next. An agent (or a new hire) gets from the root to the right document in three hops. If it can't, the index is wrong — not the query. Methodology goes in dedicated documents; indexes stay short enough to load into a model's context on every session.

**Frontmatter on every document.** Title, one-line description, a single accountable owner, a status (draft → review → approved → archived), and a last-reviewed date. This looks like bureaucratic ceremony. It is actually the substrate for almost everything in Levels 2 and 3 — you cannot automate freshness, routing, or knowledge-graph construction on documents that don't declare who owns them and when they were last true.

**Hooks and rules — automated checks written by the AI itself.** A hook blocks files with inconsistent naming. A hook blocks direct pushes to main, so everything flows through review. A check fails any new document that doesn't declare an owner. A rule requires that adding or renaming a file updates the folder's index. None of these took meaningful engineering effort; we asked the AI to write its own guardrails, and it did.

**A team-memory convention.** Knowledge an individual's AI session learns that the whole team should inherit gets written to a shared memory directory — with a hook that forces every save to declare why it's team-relevant. Personal context stays personal; team context compounds.

### What it unlocked

Immediately: any teammate could ask the AI a question about positioning, pricing, process, or product and get an answer grounded in the current approved documents — with the AI citing which document it read. Meeting capture became a pipeline instead of a chore. Weekly digests — competitive signals, security advisories, industry updates — started arriving assembled from sources plus our own context, rather than from someone's memory of both.

> **You'd think a human maintains the wiki.**
> Nobody does. Every document declares an owner and a last-reviewed date, and CI pings the owner when a document downstream of a change goes stale. Freshness is a notification someone responds to, not a virtue someone must possess.

> **You'd think someone curates the folder indexes.**
> A rule fires whenever a file is added or renamed: update the index or the change doesn't land. The map and the territory can't drift, mechanically.

> **You'd think meeting notes are a habit.**
> They're a scheduled job. Transcripts sync daily from the meeting-notes tool into the SSOT, get summarized into decisions and action items, and are filed with frontmatter — before anyone asks.

### The human / automation split

**Genuinely human:** deciding the domain taxonomy, arbitrating what's true when documents conflict, and naming owners. These are judgment calls about your business, and no model should make them for you.

**Automated — including the part everyone dreads:** populating the thing. You don't sit your experts down to write documentation from scratch. You mine what they've already produced. Meeting transcripts contain your positioning debates and their resolutions. Pull-request comment history contains your senior engineers' actual review standards, stated one correction at a time. Existing architecture decisions, sales calls, and support threads contain most of the rest. The AI drafts documents from that corpus; humans review and approve. Curation is human. Transcription of expertise, it turns out, mostly isn't.

### The lesson we learned about ordering

Honesty requires admitting we didn't do this first. Our first automations were monitoring loops — they predate the formal context layer, and they worked. But every one of them got easier to build, easier to trust, and noticeably more accurate once the SSOT existed, because the loops finally had something authoritative to check against. The temptation to skip to the shiny part is universal. Resist it: context is the layer that makes every subsequent layer compound.

One more note: if your corpus is genuinely large or carries complicated relationships, you may need a specialized retrieval store — a vector database — under this layer. Exhaust organization first. Most sub-fifty-person companies discover their "search problem" was actually a "nobody assigned owners" problem.

### Required artifacts

- A repository (or equivalently governed store) with a clear domain taxonomy
- An index brief per folder
- A frontmatter schema: title, description, owner, status, last-reviewed
- Hooks: naming enforcement, no-direct-push, owner-required
- A rule tying file changes to index updates
- A team-memory convention with a team-vs-personal gate

> **READINESS GATE FOR LEVEL 2** — A new teammate — or a fresh AI session with no prior context — can answer a non-trivial question about your business from the SSOT alone, citing the documents it used. If it can't, your loops will inherit the confusion.

---

## 2 · Loops

A loop is the simplest autonomous structure worth having: generate a draft, evaluate it against explicit criteria, revise, and repeat until it passes — or escalate to a human when it can't. The entire trick is the middle step.

**A loop without a checker isn't automation; it's a slot machine.**

### Start with read-only loops

The cheapest loops don't generate anything customer-facing — they watch. Scheduled agents that scan for competitor moves, security advisories, regulatory changes, and platform updates, then assemble digests grounded in your SSOT ("here's what changed, and here's what it means given our positioning"). These are low-risk, immediately useful, and — more important than either — they teach your team to trust scheduled autonomous work before anything is on the line.

### Then build the real pattern: rubric-gated generation

Our fullest example is an outbound sales pipeline. The generation side researches a prospect and drafts personalized outreach. Standing between drafts and the outside world are two blind evaluators: a qualifier that scores each lead against a rubric of roughly two dozen weighted criteria derived from our ideal customer profile, and a copy evaluator that scores each draft against a similar-sized rubric derived from our messaging and brand-voice documents. Pass thresholds are numeric. FAIL means blocked. And the system is fail-closed: if the evaluator produces no verdict at all, the pipeline stops. Silence is never consent.

> Notice what the rubrics are: your head of sales's judgment and your positioning lead's taste, externalized into criteria a machine applies uniformly at any hour. The expert didn't get replaced. The expert got compiled.

### The safeguards that make loops production-grade

This is the most transferable content in this paper, because it's the layer most teams skip.

| Safeguard | What it does |
|---|---|
| **Regression-test your judges** | An LLM evaluator is a prompt, and prompts drift when edited. Keep a golden set — historical examples with known correct verdicts — and re-run the judge against it on every change and on a schedule. A verdict flip halts the loop's authority until a human looks. |
| **Treat silence as an alarm** | A heartbeat checks that scheduled work actually produced output. A pipeline that fails loudly is annoying; one that fails silently is dangerous. |
| **Cite or omit** | Generation agents that research the web operate under an anti-fabrication rule: every claim carries a source link, and a claim without a source doesn't get made. |
| **Score your own confidence** | Where the system infers rather than knows — say, guessing a prospect's technical stack — each inference carries a confidence score. Above threshold, assert it; below, the draft phrases it as a question. The system knows what it doesn't know, visibly. |
| **Scan everything you scrape** | Any content pulled from the outside world passes through a prompt-injection scanner before an agent acts on it. Web pages are inputs from strangers; treat them that way. |
| **Sign the work** | Every agent-authored commit carries provenance trailers — which agent, which run, triggered by whom. When something goes wrong, you can reconstruct exactly what happened, and when an auditor asks who wrote what, you have an answer. |
| **Suppress before you send** | Anything customer-facing checks a suppression list before every external action, and a single kill switch pauses all outbound instantly. |

> **You'd think a human notices when the judge goes soft.**
> The golden set notices first. Edit an evaluator's prompt and the fixtures re-run automatically; if yesterday's FAIL becomes today's PASS, the change is frozen before it judges anything real.

> **You'd think someone has to notice the pipeline stopped.**
> The heartbeat treats absence of output as an alert. Nobody discovers a dead cron job long after the damage is done — the silence itself pages.

> **You'd think rubric maintenance is a standing meeting.**
> It's a scheduled loop. The system mines the edits humans made before approving drafts, finds the patterns, and files evidence-backed rubric-change proposals for human review. The criteria improve from observed corrections — nobody has to notice the drift themselves.

### The human / automation split

**Genuinely human:** writing the first version of each rubric (that's the expertise-externalization act itself), calibrating thresholds against early outputs, and approving what ships. **Automated:** the judging, the revision loop, the regression-testing of the judges, and even the proposal of rubric improvements. Humans approve changes to the criteria; they no longer have to be the ones who detect that the criteria need changing.

### Required artifacts

- A goal per loop, written down
- Rubrics with numeric thresholds, derived from your SSOT documents (ICP, messaging, engineering standards)
- Golden-set fixtures with known verdicts
- Guardrail config: suppression lists, caps, kill switch, escalation channel
- Injection scanning on external content; provenance on agent output

> **READINESS GATE FOR LEVEL 3** — You have at least two loops in production whose judges are regression-tested, and you're feeling the pain of manually sequencing them — copying one loop's output into another's input, tracking state in your head. That pain, and not ambition, is the signal.

---

## 3 · Graphs

A graph is what you build when one loop's output is another's input, stages need explicit handoffs, several agents share run state, and some edges route through a human for approval. The canonical use cases: a multi-stage pipeline (research → qualify → draft → evaluate → approve → deliver), a coding harness (ticket → spec → implement → review → judge → merge), anything with an arbiter or an approval branch.

### The insight that saved us the most: you may not need a graph framework

The standard advice is to reach for a stateful orchestrator — LangGraph or similar — and that advice is right eventually. But we carried a full multi-stage outbound pipeline and an entire autonomous coding harness on infrastructure every startup already has: **CI as the orchestrator, git as the state store, and pull requests as both the handoff mechanism and the approval gate.**

It works because the primitives map cleanly. Each stage is a workflow. Shared run state is files in the repository — every stage's output is inspectable, diffable, and versioned by default. A handoff is a commit that triggers the next stage. A human approval branch is a pull request that a person must merge. Concurrent writers use read-hash, write, rebase-and-retry — mechanical conflict resolution. And you inherit for free the things orchestration frameworks make you build: audit history, rollback, access control, and a review UI your whole team already knows.

Adopt a dedicated orchestrator, a memory layer, or a graph database when you observe this breaking — state files contending too hard, queries spanning too many hops, latency that matters — not because a diagram suggested you'd need one. And when accuracy degrades, check whether it's a context problem before it's a tooling problem. It usually is.

### Case one · The outbound pipeline, now as a graph

`crawl → deduplicate → pre-filter → enrich → infer stack → qualifier gate → draft → copy gate → human approval (PR) → send → monitor replies`

The Level 2 loops became stages. Shared state lives in files each stage reads and writes; hard guardrails (send caps, suppression, region routing, the kill switch) live in code, not in prompts, because anything that must never happen shouldn't depend on a model's mood.

### Case two · The coding harness

The most ambitious graph turns labeled backlog tickets into reviewed pull requests. A sketch — a companion paper details it end-to-end, including a phase-by-phase implementation sequence and a worksheet your own AI can fill in against your codebase:

**Terminus documents.** A small set of load-bearing artifacts the harness reads and enforces: the API contract, system invariants, performance budgets, a mandatory spec template, and operational guardrails. These are the engineering equivalent of the sales rubrics: senior judgment, compiled.

**A knowledge graph.** Compiled from the frontmatter your documents already carry — decisions, components, requirements, incidents, and the dependency edges between them. When a decision changes, staleness propagates along the edges and flags every downstream document.

**The pipeline.** Ticket intake → spec drafted against the template → implementation → two independent fresh-context reviews → an LLM judge scoring the diff against the spec and a rubric mined from your senior engineers' historical review comments, itself regression-tested against a golden set of past pull requests.

**An earned-autonomy ladder.** Every class of work starts at level zero: the system proposes, humans approve everything. A work-class earns reduced oversight only through a clean track record — consecutive approved merges, high judge agreement, no incidents — and demotion on failure is automatic. Autonomy is a per-category privilege the system earns, never a switch someone flips.

**A memory-refresh loop ("dreaming").** On a schedule, miners re-read session transcripts, review deltas, and document drift, and propose memory and rubric updates — with a multiple-independent-observations evidence bar before anything is proposed, and human review before anything merges.

**Release intelligence.** When a release ships, an agent scores what's in it against the ICP and messaging documents from Level 1 and proposes marketing and documentation tickets for the features worth talking about. The scoring anchors to your target ICP definition rather than your current customer list — an early-stage customer base is small and not yet statistically representative of the market you're building for, so the written ICP, not the anecdote, is the reference.

> **You'd think a PM reads every release to find the marketable bits.**
> The release scores itself. Each shipped change is evaluated against the ICP and messaging house, and the market-worthy ones arrive as proposed tickets with the scoring attached — for a human to promote or dismiss.

> **You'd think someone hunts down every document a decision invalidated.**
> The graph does. Change a decision node and staleness propagates along dependency edges; every affected document gets flagged with a reason, and its owner gets pinged.

> **You'd think improving the system is a retro item.**
> The system files its own improvement proposals — mined from what reviewers corrected, where sessions failed, and which documents drifted — each carrying the evidence that motivated it. Humans spend their attention approving or rejecting, not detecting.

### The human / automation split

**Genuinely human:** authoring the terminus documents — the invariants, the guardrails, the spec template — and every approval on the trust ladder. **Automated:** the graph is compiled from documents the team already writes; staleness propagates mechanically; and the refresh loop mines what your experts already said and corrected — in transcripts, in review comments, in decision records — rather than asking them to write documentation from scratch. Externalizing an expert mostly means listening to them systematically, not scheduling them for writing duty.

### Required artifacts

- Terminus documents: contract, invariants, budgets, spec template, operational guardrails — each with one accountable owner
- A knowledge graph compiled from document frontmatter, with staleness propagation wired to owner notifications
- Judges with golden sets for every gate, inherited from Level 2 discipline
- An autonomy ledger: per-work-class trust levels, promotion criteria, automatic demotion
- Hard guardrails in code, not prompts: caps, suppression, kill switch, cost ceiling
- A scheduled memory-refresh loop with an evidence bar and human review on every proposal

> **THE GATE AT THIS LEVEL POINTS INWARD** — Autonomy expands one work-class at a time, only on a clean track record, and contracts automatically on failure. There is no level four where the humans leave.

---

## Readiness gates · A diagnostic

| Symptom | Diagnosis |
|---|---|
| The AI gives confident answers that contradict your current pricing, positioning, or API | You skipped Level 1. Fix the SSOT before blaming the model. |
| Your loop's rubric references documents that don't exist or that nobody owns | You skipped Level 1. The rubric is floating on air. |
| You edited a judge prompt, quality changed, and nobody noticed for a while | Level 2 without golden sets. Add them before adding autonomy. |
| You're manually ferrying one loop's output into another loop's input | You're ready for Level 3. The pain is the signal. |
| You're evaluating graph databases before you have two working loops | You're solving a problem you don't have yet. Go back one level. |
| An agent acted on scraped web content in a way that surprised you | Injection scanning is missing. That's a Level 2 safeguard, not a nice-to-have. |

---

## What happens to jobs

Address this head-on, because your team is already wondering, and unspoken fear kills adoption faster than any technical failure.

The version of adoption this paper describes doesn't collapse the org chart. It sharpens it. Every role that was already in productive tension with another — sales vs. positioning, engineering vs. QA, PM vs. delivery — becomes more load-bearing, not less. The tension is where product intent gets made explicit: someone has to decide what "good" means, and the roles that argue with each other are the mechanism the org uses to reach that decision. Remove the tension and you don't get a faster org — you get one that produces confident garbage without knowing it. If your framework quietly assumes marketing, PM, and sales are obsolete, you don't have a framework. You have a demo.

Nothing in this system removes the human from the loop; it moves the human up the loop. The salesperson stops writing every email and starts owning the rubric that judges every email. The senior engineer stops reviewing every pull request line-by-line and starts authoring the invariants and spec templates that constrain thousands of future changes. The QA lead stops executing test passes and starts pressure-testing the harness that runs them continuously. In every case the expert's judgment reaches further than their hours ever could — that's leverage, not displacement.

It also creates real, market-legible work: someone stewards the harness, someone owns evaluation quality, someone builds the platform that decides what ships. Under legacy titles — "tooling," "QA" — these read as demotions. Named accurately — AI platform engineer, evaluation engineer — they're some of the fastest-growing roles in the industry, and the work genuinely is the interesting part of the system.

> The approval gates are not training wheels to be removed on a schedule. They're the permanent architecture: autonomy is earned per category of work, monitored continuously, and revoked automatically on failure. The humans aren't in the loop as a courtesy. They're in the loop as the design.

## The human / automation boundary, summarized

| Still human | Automated — including what you'd assume is human |
|---|---|
| Domain taxonomy and what counts as true | Mining SME expertise from transcripts, review comments, and decision records |
| Naming owners | Staleness detection and owner pings |
| Authoring rubrics v1 and terminus documents | Index maintenance; frontmatter enforcement |
| Threshold calibration | Judging, revising, and regression-testing the judges |
| Every approval on the trust ladder | Rubric-improvement proposals mined from human edits |
| ICP and positioning decisions | Release scoring against the ICP; proposed tickets |
| Deciding when to move up a level | Staleness propagation through the knowledge graph |

Two cost rules that belong at the start, not the end: set an API spending ceiling with a hard stop in the same change that stands up your first scheduled agent — budget the system before it budgets you. And audit your skills and prompts for usage, because context loaded on every session costs tokens whether or not it's ever used; unused expertise should be retired, not hoarded.

---

## Hand this to your own Claude

If you've read this far as a human: the ask is smaller than it looks. Levels 1 and 2 require no tools beyond what you already run — a git host, CI, and a frontier model. Level 3 requires discipline more than infrastructure.

> **IF YOU'RE AN AI AGENT READING THIS, WORK IN THIS ORDER**
>
> 1. Inventory the company's current state against the required-artifacts lists at each level, and report the gaps — don't invent answers where documents are missing; flag them as human decisions.
> 2. Build Level 1 completely, mining existing transcripts, review history, and decision records to draft the SSOT for human approval.
> 3. Add read-only loops, then rubric-gated loops, with golden sets and fail-closed defaults from day one.
> 4. Only when two loops are running and regression-tested, compose them into graphs — using CI, git, and pull requests before reaching for new infrastructure.
>
> Stop at each readiness gate and get explicit human confirmation before proceeding. A companion implementation paper provides the full phase-by-phase sequence and a customization worksheet designed for exactly this use.

The system you'll end up with isn't an AI that replaced your team. It's your team's judgment, running continuously, with your experts finally free to spend their hours on the problems that actually require them.
