---
title: "Single source of truth"
description: "What to build so people and Claude Code share one checked set of docs, the research behind each choice, and the two prompts that build it."
owner: charlcye
status: draft
last_reviewed: 2026-11-14
---

# Single source of truth

Everything else in this cookbook reads your docs and trusts them. This chapter builds the part that makes them worth trusting.

It is a snapshot dated 2026-11-14, written for one person who owns the whole system and uses Claude Code. Each design choice was judged on four words: does it help produce reliable, secure, working products, efficiently?

## The prompts

| # | Prompt | What it adds | You'll know it works when |
|---|---|---|---|
| 1 | [The checked docs repo](prompt-1-checked-docs.md) | Required fields, a generated index, sources and an approver on approved docs, one script in CI, a weekly stale list | Deleting a doc's owner fails the check |
| 2 | [Wire it for Claude](prompt-2-wire-for-claude.md) | A short map Claude loads at the start, one scoped rule file, a hook that runs the checks before Claude finishes, an owners file | Claude is shown a broken doc before it finishes a turn |

Do them in order. The second assumes the first.

## What we decided, and why

### Truth lives in Markdown in a git repo, changed by pull request

We found no comparison showing that any other store works better for coding agents, so we kept git.

- Three teams that build coding agents dropped separate search indexes in favour of searching files directly. Their reasons were the same: an index goes stale, and it is a second copy to secure. [1][2][3]
- The results that favour search indexes are about finding things in large collections, not about where truth is written. One study found keyword search overtakes file search at roughly 10 million tokens (one source). [4] One vendor found that adding semantic search to file search improved its agent's answers, with the larger gain on large repos (one source). [5]
- Wiki tools can be reached by agents, but we found no write-up showing an agent doing better work from a wiki than from a repo.

What lost: a wiki as the source, a vector store as the source, a knowledge graph. If you outgrow file search, add a search index built from the repo and treat it as disposable.

The strongest argument against this choice: people who don't use git will keep writing elsewhere, and the agent never sees it. For a solo operator that is a matter of habit. For a team it needs an easy way in, such as an agent that drafts the pull request for a person to approve.

### Rules that matter are checks in CI, not instructions

- Claude Code's documentation says instruction files are treated "as context, not enforced configuration", with no guarantee of strict compliance. [6]
- One author's three-month report on his own agent-maintained wiki found the same thing in practice: agents respected a failing check and drifted past written rules (one source). [7]
- CI sees every change, whoever made it. A hook only runs in Claude Code sessions that load it. That second sentence is our inference, not a statement in the documentation.
- CI only enforces once the repository requires the check and nobody can bypass it. Until then, everything in this chapter is advisory.

So the fields, the index, the links, the sources and the hidden-character scan are all one script, run on every pull request. The job is not limited to certain paths, because a skipped check can't be made required.

What lost: rules only, and hooks only.

### The hook is for fast feedback

Prompt 2 adds a hook that runs the same script when Claude is about to finish and shows it any problems. The aim is to save a round trip through CI. It is not the enforcement: after two failed attempts it lets Claude stop. In eight real sessions it never caused a repair: when Claude was allowed to run the check, it ran it unprompted, and when the request ruled out the fix, Claude followed the request. What the hook did do was warn the operator that a turn had ended with the docs failing. We kept it for that warning. It does nothing on turns that touch no docs.

### A short map at the start, and a generated index

- Claude Code's documentation asks for instruction files under 200 lines and says longer files reduce adherence. [6]
- One study of three coding agents found instruction files don't generally raise task success, and raise cost by over 20% on average. Files written by a model scored slightly lower and files written by developers slightly higher; neither difference was statistically significant (one source). [8] That study covers instruction files in general, so it argues for keeping the file small, not for a particular size.
- One evaluation found that an index placed in the always-loaded file scored 100%. The same material offered on request scored 53%, no better than having no docs, because the agent often didn't go and look. Telling the agent to use it raised that to 79% (one source). [9]

These two findings pull against each other: one says loaded context costs money without a measured gain, the other says a pointer that isn't in view often goes unused. We settled on a root `CLAUDE.md` of at most 100 lines that imports a generated index of one line per doc. The script warns when the two together pass 200 lines, the size the documentation gives as its target. That is the point to stop importing the index and let Claude search.

The index is generated, and CI fails if it is out of date. An instruction to "keep the index updated" is exactly the kind of rule that drifts.

What lost: a hand-kept index in each folder, and no index at all.

### Five fields, three statuses

Frontmatter is well supported as something to check. We found no evidence that any particular field helps an agent find documents. So the list is short: title, description, owner, status, last reviewed. Status has three values. A longer list is harder to keep to.

### Approved docs name their sources and their approver

- The best-supported way to keep agent-written facts honest is to store each fact with a pointer to its evidence and re-check the pointer before relying on it (one source, with a measured result). [10]
- The Linux kernel's rule for coding assistants puts responsibility on a named person: the assistant can't sign off, and the person who submits is fully responsible. [11]
- We found no evidence that a "verified" label on its own improves anything. One report found about 30 pages marked authoritative that were out of date (one source). [7]

So a doc can't be `approved` without `approved_by` and at least one source, and local sources must exist. The script can't tell who typed the approver's name or whether the source supports the doc. Your review of the pull request does that.

One practice we left out: on teams, the person who asked an agent for a change shouldn't be the one who approves it. [12] A solo operator can't follow that. Read the diff before you merge.

### Stale docs surface on their own

A weekly job lists every doc nobody has confirmed in 180 days and keeps one issue in step with the list. We found no evidence that such lists make docs more accurate. They do stop the date from being decoration. We kept this from our own practice.

### Hidden characters are checked

Researchers have shown that invisible Unicode characters in shared instruction files can steer coding assistants while staying unseen in review (one source, a proof of concept). [13] The script fails on them in docs and in Claude's instruction files.

## What this chapter leaves to later ones

- Secrets, tokens and which paths an agent may touch.
- Checking that a source actually supports a claim.
- Finding two docs that contradict each other. We found no working method in production.

## Where the evidence is thin

Several findings above rest on one source and are marked. We found nothing solid on these questions:

- git Markdown against wiki tools, measured on agent task success
- how accurate an agent is when it maintains documentation
- whether stale lists or status labels improve accuracy
- the size at which a small company's repo needs a search index

Where we found nothing, we kept what we were already doing and said so.

## Sources

Dates are publication dates where the page shows one. Every page was fetched on 2026-11-14 and each claim above was checked against it.

1. Anthropic, "Effective context engineering for AI agents", 2025-09-29. <https://www.anthropic.com/research/effective-context-engineering-for-ai-agents>
2. Cline, "Why Cline Doesn't Index Your Codebase (And Why That's a Good Thing)", 2025-05-27. <https://cline.bot/blog/why-cline-doesnt-index-your-codebase-and-why-thats-a-good-thing>
3. Sourcegraph, "Cody FAQs", undated. <https://sourcegraph.com/docs/cody/faq>
4. Wang et al., "BM25 Wins at Scale: A Scaling Study of Retrieval-Augmented Generation Paradigms", 2026-07-29. <https://arxiv.org/abs/2607.26497>
5. Cursor, "Improving agent with semantic search", 2025-11-06. <https://cursor.com/blog/semsearch>
6. Anthropic, Claude Code documentation, "How Claude remembers your project", undated. <https://code.claude.com/docs/en/memory>
7. webvise, "The LLM Wiki at 490 Pages: What 3 Months of Agent-Maintained Knowledge Actually Takes", 2026-07-28. <https://www.webvise.io/en/blog/llm-wiki-3-month-report>
8. Gloaguen et al., "Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?", 2026-02-12. <https://arxiv.org/abs/2602.11988>
9. Vercel, "AGENTS.md outperforms skills in our agent evals", 2026-01-27. <https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals>
10. GitHub, "Building an agentic memory system for GitHub Copilot", 2026-01-15. <https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/>
11. Linux kernel documentation, "AI Coding Assistants", undated. <https://docs.kernel.org/7.3/process/coding-assistants.html>
12. GitHub Docs, "Risks and mitigations for GitHub Copilot cloud agent", undated. <https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/risks-and-mitigations>
13. Pillar Security, "New Vulnerability in GitHub Copilot and Cursor: How Hackers Can Weaponize Code Agents", 2025-03-18. <https://pillar.security/blog/new-vulnerability-in-github-copilot-and-cursor-how-hackers-can-weaponize-code-agents>
