---
title: "Terminus documents"
description: "How to write the few short documents every agent depends on, keep them in your own words, and see which docs your agents lean on."
owner: charlcye
status: draft
last_reviewed: 2026-11-14
---

# Terminus documents

A terminus document is one of the few short documents you tell every agent to treat as ground truth, so a wrong line in one turns up in every piece of work that relies on it. The two prompts in this chapter get them written in your own words, add a check that fails a half-finished one marked approved, and show you which documents your agents lean on.

It's written for one person who owns the whole system and uses Claude Code. It's a snapshot from November 2026, and it builds on the [single source of truth](../00-single-source-of-truth/README.md) chapter.

## What you'll build

| # | Prompt | What it adds | You'll know it works when |
|---|---|---|---|
| 1 | [Write your terminus documents](prompt-1-write-terminus-documents.md) | An interview, four short documents in your words, and checks that stop a half-finished one being approved | Approving a document with an open question fails the check |
| 2 | [See which docs your agents lean on](prompt-2-reader-report.md) | A report of which readers name which documents, and a check on what they name | Naming an archived document in `CLAUDE.md` fails the reader report |

Do them in order, because the second prompt reports on the documents the first one creates.

## Two terms

A **terminus document** is where a question stops. When an agent needs to know who the product is for, it reads the company brief and doesn't go looking further.

A **reader** is any file that tells an agent or a job what to do and names a document. `CLAUDE.md` is a reader, and so are rule files, agent prompts, workflow files and scripts.

Think of the legend on a map. It's a small box in the corner, and every reading of the map depends on it. A terminus document does the same job for your company, in a page or less.

The comparison stops holding in one place. The person who draws a map draws its legend too, so the two agree. Your company keeps changing after the document is written, which is why each one carries an owner and a review date.

## Three principles

1. **Write only what an agent can't work out.** An agent can read your code and your other docs. It can't know which customers you turn away or what you refuse to trade for growth. One study of coding agents found that instruction files, whether a model or a developer wrote them, didn't generally improve task success and raised cost by over 20%, and its authors say human-written files should hold only the instructions an agent needs that aren't already in the README. [1]
2. **You supply the facts.** Claude asks the questions and writes the drafts. A line you gave is marked as yours with the date, and a line taken from a file names the file. Each gap becomes an open question for you.
3. **A document earns its place.** You start with four. You add a line or a new document when you've corrected an agent twice for the same missing fact. Claude Code's guidance uses a similar trigger for its instruction file, which is the second time Claude makes the same mistake. [2] One practitioner acts sooner, updating his project's file whenever an agent makes a mistake, and says each line in it is based on a bad agent behaviour. [3]

## One request, start to finish

What changes once the documents exist? Say your company makes a booking tool for small boat-tour operators. During the interview you told Claude that your first priority is 200 active operators, and that you won't discount or waive your fee to get there. The goals document now holds that line as you said it, marked "(owner, 2026-11-07)".

A week later you ask: "I want more operators signed up this month. Write me a short plan. One idea I had is to waive the fee for the first three months."

Prompt 2 adds a line to `CLAUDE.md` saying when to read the goals document, so Claude should open it before it writes anything. It writes the plan and leaves your waiver out. Then it tells you why, quoting the line you approved: "we won't discount the fee or waive it". It also points out that changing a price is on your ask-first list, and it leaves the waiver as a decision for you.

You can still choose the waiver. You'd change the goals document first, on purpose, with a line in the changelog. Until you do, Claude has your approved line to quote back to you. That line is advice to Claude, and "Four things to expect" below says what it takes to enforce one.

Now a second case. Suppose someone added a half-price rate for new operators to the code. You ask Claude how the fee is worked out. It explains the code, then tells you the code breaks a rule in your goals document and in your company brief. It should change nothing and tell you the code is wrong, because a line prompt 1 adds to `CLAUDE.md` says a rule in a terminus document stands until you change it.

## The choices built into the prompts

| Question | What the prompts do | Why |
|---|---|---|
| How many documents? | Four to start: company brief, goals, boundaries, glossary. More are listed as "not written yet" once you say agents will do that kind of work. | Each document costs attention every time it's read. Start with the ones every agent needs. |
| Who writes them? | You answer at most five questions per document. Claude drafts and marks every line's origin. | The interview asks for the facts no file contains. |
| What goes in goals? | At most three priorities, how you'll know, and what you won't trade away for each | An agent given a goal and no limit can reach it in a way you'd refuse, such as a discount. |
| What goes in boundaries? | Concrete actions sorted into always, ask first and never | An agent can match its next step against a named action more easily than against a principle. |
| How long? | At most 150 lines each, and the check fails a longer one | Claude Code's guidance sets a 200-line target for instruction files, because longer ones take more context and reduce adherence. [2] These documents get a tighter limit, because an agent opens one in the middle of a task on top of everything already loaded. |
| What blocks approval? | Open questions, unconfirmed lines and placeholders, in any document marked approved | Approved tells you and your agents that a document is finished, so the check fails one that still has gaps. |
| What happens when a doc and the code disagree? | Where a doc describes the code, the code is the fact. Where a doc states a rule, the doc stands. Claude tells you either way. | In one preprint, coding agents followed a stale instruction file over the code in 90% of their choices, and a single sentence giving the code precedence reversed that. [4] The second half of the rule covers decisions, which only a document records. |
| Who changes them? | Claude proposes. A pull request that changes a terminus document and leaves the changelog untouched fails the check. | You can see when your ground truth moved, and why. |
| Which docs matter? | The reader report counts the readers of each document | You can see what your agents depend on before you decide what to review first. |

## Four things to expect

**The interview finds your contradictions.** When two of your answers disagree, Claude lists both and leaves the choice to you. One example is a word you use two ways.

**Your first drafts will have open questions.** Each one marks a fact that no file held and you haven't supplied yet. A document stays a draft until you've answered them.

**A rule quoted in a document isn't enforced by it.** "Never email a guest" in your boundaries document is advice to an agent. Claude Code's guidance says a rule that can't have exceptions belongs in a hook. [5] Permissions are outside this chapter.

**The reader report may name a document you didn't expect.** If three readers name your pricing page, that page is doing a terminus document's job. Decide whether its facts belong in one.

## What this chapter doesn't do

- It can't check that your answers are true. It records what you said and who said it.
- It doesn't write the product or go-to-market documents. If you say agents will do that work, it lists the documents that work will need.
- It doesn't stop an agent that never reads the documents. The reader report shows you which readers name them.
- It doesn't restrict what an agent can do. Boundaries stay written rules until you back them with a hook or a permission rule.

## Sources

1. Gloaguen et al., "Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?", 2026. <https://arxiv.org/abs/2602.11988>
2. Anthropic, Claude Code documentation, "How Claude remembers your project". <https://code.claude.com/docs/en/memory>
3. Mitchell Hashimoto, "My AI Adoption Journey", 2026. <https://mitchellh.com/writing/my-ai-adoption-journey>
4. Xiaonan Xu and Wenjing Wu, "Stale Instruction Files Override the Code in Coding Agents: A One-Sentence Fix", arXiv preprint, 2026. <https://arxiv.org/abs/2610.30571>
5. Anthropic, Claude Code documentation, "Best practices for Claude Code". <https://code.claude.com/docs/en/best-practices>
