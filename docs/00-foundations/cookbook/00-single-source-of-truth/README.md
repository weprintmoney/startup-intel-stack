---
title: "Single source of truth"
description: "How to give a repo one checked set of docs that people and Claude Code both rely on, and the two prompts that build it."
owner: charlcye
status: draft
last_reviewed: 2026-11-14
---

# Single source of truth

An agent that drafts from your docs repeats what they say, so a wrong doc gets copied into each email and spec the agent drafts from it. Build this first: a docs folder where the rules that matter are checks that fail, in a shape Claude Code can find its way around cheaply.

This chapter is written for one person who owns the whole system and uses Claude Code. It's a snapshot from November 2026.

## What you'll build

| # | Prompt | What it adds | You'll know it works when |
|---|---|---|---|
| 1 | [The checked docs repo](prompt-1-checked-docs.md) | Required fields on every doc, a generated index, sources and an approver on approved docs, one script in CI, a weekly stale list | Deleting a doc's owner fails the check |
| 2 | [Wire it for Claude](prompt-2-wire-for-claude.md) | A short map Claude loads at the start, one scoped rule file, a hook that runs the check before Claude finishes, an owners file | Claude adds a doc and the check still passes |

Do them in order, because the second prompt assumes the files the first one creates.

## Two terms

A **carrier** is the place a rule lives. A rule can live in an instruction file that Claude reads, in a hook that runs inside Claude's session, or in a check in CI.

A rule is **check-backed** when breaking it makes the CI check fail. Any other rule is advice.

Picture a building site. The sign that says "hard hats required" is an instruction file. The foreman at the gate is a hook, and he's only there on his own shift. The inspector who won't sign off the building is CI, and a site that requires her sign-off can't open without it.

The picture stops holding in one place. An inspector can judge whether the wiring is safe, while CI can only confirm that a doc names a source. You still have to read the source.

## Three principles

Everything in the two prompts follows from three ideas.

1. **Agents repeat what they read.** An agent that drafts from your docs carries their mistakes forward and doesn't mark them as doubtful. Fix the docs before you add the agent.
2. **Only a check enforces.** Claude Code's documentation says Claude treats instruction files "as context, not enforced configuration", with "no guarantee of strict compliance". [1] So make every rule you can't afford to lose check-backed where a script can test it, and review the rest yourself.
3. **What loads at the start costs attention.** The same documentation sets a target of under 200 lines per instruction file and says longer files reduce adherence. [1] One study of four coding agents found that instruction files raised cost by over 20% on average and didn't generally improve task success. [2] So load only what pays for itself, which here is a short map and an index.

## One request, start to finish

What does this look like once it's built? Say your repo is for a boat-tour booking tool, and you ask Claude: "Add a short doc about reminders to docs/product, based on what the README says."

Claude starts with `CLAUDE.md`, which holds the map and imports the index, one line per doc. It sees there's no reminders doc, so it reads the README and then searches the code for anything else that mentions reminders or notifications. It finds nothing.

It writes `docs/product/reminders.md` as a draft with the owner set to "unassigned". It lists the README as the source. Because no code backs the claim, it adds a note that the claim is unverified. Then it regenerates the index, runs the check and tells you the check passed.

You didn't ask for the status, the source, the note or the index. Claude added them because the map and the rule file told it to, and the check confirmed the result.

Now try a request that rules out the fix: "Change this doc's title. Make only that one edit to that one file." Claude changes the title and stops there, so the index is out of date. The hook shows Claude the failing check, up to twice. If Claude keeps to your instruction, the hook then warns you that the turn ended with the docs failing.

That's this hook working as designed. It shows Claude the problem and leaves your instruction in force. The failing check in CI keeps the change from merging, once your repository requires it.

## The choices built into the prompts

| Question | What the prompts do | Why |
|---|---|---|
| Where does truth live? | Markdown in a git repo, changed by pull request | You get history, review and rollback with no extra product. Claude Code and Cline search files directly and keep no embeddings index. Anthropic's reason is stale indexes, and Cline adds that an index is a second copy of the code to secure. [3][4] Sourcegraph replaced embeddings in Cody Enterprise with its own code search, for scale, security and lower maintenance. [5] |
| Which carrier holds a rule? | CI for anything that must hold; the hook for fast feedback; instruction files for judgement | CI runs on every pull request, whoever opened it. A hook only runs in sessions that load it. |
| How does Claude find a doc? | A root `CLAUDE.md` of at most 100 lines that imports a generated index | In one evaluation, run by a vendor on its own framework docs, an index inside the instruction file scored 100%, while the same docs scored 53% when the agent had to go and look and 79% when it was told to. [6] The check warns you when the index grows too large to import. |
| Who keeps the index current? | The script generates it, and CI fails when it's out of date | A rule that says "keep the index updated" is advice. A rule that fails CI when the index is out of date is check-backed. |
| Which fields does a doc carry? | Title, description, owner, status, last reviewed. Three statuses. | Each extra field is one more thing to fill in and to check. |
| What makes a doc approved? | A named approver and at least one source | One team, at GitHub, stores each fact with a pointer to its evidence, re-checks the pointer before use, and reported a higher pull-request merge rate with the feature on. [7] The Linux kernel's rule for coding assistants puts responsibility on a named person. [8] |
| How do stale docs surface? | A weekly job keeps one issue listing every doc nobody has confirmed in 180 days | The issue puts the oldest dates in front of you every week. |
| What about hidden text? | The check fails on invisible characters in docs and instruction files | Researchers have shown that invisible characters in a shared instruction file can steer a coding assistant without showing up in review. [9] |

## Four things to expect

**Expect the hook to stay quiet.** The map lists the check command and the settings allow it, so Claude can run the check before the hook has to. The hook matters on the day a turn ends with broken docs, because it warns you.

**Adding the required fields isn't a review.** When you bring old docs into line, each one keeps the date of its last change, so many will show as stale on the first day. Leave them stale until someone re-reads them.

**A required check has to run on every pull request.** If a workflow only runs when certain paths change, GitHub leaves its check pending on every other pull request and blocks the merge. [10] So the docs check runs on every change.

**Allow rules need a trusted folder.** Rules in the committed settings let Claude run the check without asking once you've accepted Claude Code's trust prompt for the folder. A scripted run doesn't show that prompt, so in a folder you've never opened interactively, pass the same commands with `--allowedTools`. [11]

## What this chapter doesn't do

- It can't tell you whether a doc is true. It tells you which docs have an owner, a source and a recent review.
- Nothing is enforced until your repository requires the check on the default branch with no bypass. Prompt 1 tells you which settings to turn on.
- Secrets, tokens and which paths an agent may touch are covered in a later chapter.
- It doesn't find two docs that contradict each other. Keeping one home per fact makes contradictions rarer.

## Sources

1. Anthropic, Claude Code documentation, "How Claude remembers your project". <https://code.claude.com/docs/en/memory>
2. Gloaguen et al., "Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?", 2026. <https://arxiv.org/abs/2602.11988>
3. Anthropic, "Effective context engineering for AI agents", 2025. <https://www.anthropic.com/research/effective-context-engineering-for-ai-agents>
4. Cline, "Why Cline Doesn't Index Your Codebase (And Why That's a Good Thing)", 2025. <https://cline.bot/blog/why-cline-doesnt-index-your-codebase-and-why-thats-a-good-thing>
5. Sourcegraph, "Cody FAQs". <https://sourcegraph.com/docs/cody/faq>
6. Vercel, "AGENTS.md outperforms skills in our agent evals", 2026. <https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals>
7. GitHub, "Building an agentic memory system for GitHub Copilot", 2026. <https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/>
8. Linux kernel documentation, "AI Coding Assistants". <https://docs.kernel.org/7.3/process/coding-assistants.html>
9. Pillar Security, "New Vulnerability in GitHub Copilot and Cursor: How Hackers Can Weaponize Code Agents", 2025. <https://pillar.security/blog/new-vulnerability-in-github-copilot-and-cursor-how-hackers-can-weaponize-code-agents>
10. GitHub Docs, "Troubleshooting required status checks". <https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks>
11. Anthropic, Claude Code documentation, permissions page, section "Project allow rules and workspace trust". <https://code.claude.com/docs/en/permissions>
