---
title: "Single source of truth"
description: "How to give a repo one checked set of docs that people and Claude Code both rely on, and the two prompts that build it."
owner: charlcye
status: draft
last_reviewed: 2026-11-14
---

# Single source of truth

In this chapter you set up a docs folder that both you and Claude Code can trust. Every doc in it says who owns it, what state it's in and when someone last confirmed it. A script checks those rules on every change, and Claude Code loads a short map of the folder so it can find the right doc quickly.

Do this before you build anything else. An agent that drafts from your docs repeats what they say, and it doesn't flag what it isn't sure of. One wrong doc ends up in every email and spec the agent writes from it, so fix the docs before you add the agent.

The chapter assumes you're the only person who owns the system and that you use Claude Code. It describes the tools as they were in November 2026.

## The two prompts

Run them in order. The second prompt expects the files the first one creates.

1. **[The checked docs repo](prompt-1-checked-docs.md).** Adds required fields to every doc, a generated index, a source and an approver on every approved doc, one check script that runs in CI, and a weekly list of stale docs. To test it, delete a doc's owner: the check should fail.
2. **[Wire it for Claude](prompt-2-wire-for-claude.md).** Adds a short map that Claude loads when a session starts, one rule file for writing docs, a hook that runs the check before Claude finishes, and an owners file. To test it, ask Claude to add a doc: the check should still pass.

The rest of this page explains how the pieces fit together, so you know what each part does when you see it in action.

## Where a rule can live

A rule in this setup can live in one of three places, called **carriers**:

- an **instruction file** that Claude reads, such as `CLAUDE.md`
- a **hook**, which runs inside Claude's session
- a **check in CI**, which runs on every pull request

They aren't equally strong. Think of a building site. The "hard hats required" sign is the instruction file. The foreman at the gate is the hook, and he only works his own shift. The inspector is CI: if the site needs her sign-off, it can't open without it. The comparison has one limit. An inspector can judge whether the wiring is safe, but CI can only confirm that a doc names a source. You still have to read the source.

A rule is **check-backed** when breaking it makes the CI check fail. Every other rule is advice, however firmly it's worded. Claude Code's own documentation says Claude treats instruction files "as context, not enforced configuration", with "no guarantee of strict compliance". [1] So if a script can test a rule you can't afford to lose, make it check-backed. Review the rest yourself.

That gives each carrier its job:

- **CI** holds anything that must hold. It runs on every pull request, whoever opened it.
- **The hook** gives Claude fast feedback. It only runs in sessions that load it.
- **Instruction files** cover judgement, the things a script can't test.

Instruction files also have a cost. Whatever Claude loads at the start of a session takes up its attention. The same documentation sets a target of under 200 lines per instruction file and says longer files reduce adherence. [1] One study of four coding agents found that instruction files raised cost by over 20% on average and didn't generally improve task success. [2] So the prompts load only what earns its place: a short map and an index.

## A request, from start to finish

Here is the finished setup at work. Suppose your repo holds a booking tool for boat tours, and you ask Claude: "Add a short doc about reminders to docs/product, based on what the README says."

1. Claude starts with `CLAUDE.md`. It holds the map of the repo and imports the index, which lists every doc on one line.
2. The index shows there's no reminders doc yet. Claude reads the README, then searches the code for anything else about reminders or notifications. It finds nothing.
3. It writes `docs/product/reminders.md` as a draft, with the owner set to "unassigned" and the README listed as the source. No code backs the claim, so it adds a note that the claim is unverified.
4. It regenerates the index, runs the check and tells you the check passed.

You didn't ask for the status, the source, the note or the new index entry. The map and the rule file told Claude to add them, and the check confirmed it did.

Now give an instruction that rules out the fix: "Change this doc's title. Make only that one edit to that one file." Claude changes the title and stops, which leaves the index out of date. The hook shows Claude the failing check, up to twice. If Claude sticks to your instruction, the hook then warns you that the turn ended with the docs failing.

The hook is working as designed here. It tells Claude about the problem but doesn't override your instruction. What stops the change is the failing check in CI, which keeps it from merging once your repository requires that check.

## Why the prompts are built this way

**The docs are Markdown files in a git repo, changed by pull request.** That gives you history, review and rollback without another product. Claude Code and Cline search files directly and keep no embeddings index. Anthropic's reason is that indexes go stale, and Cline adds that an index is a second copy of the code to secure. [3][4] Sourcegraph replaced embeddings in Cody Enterprise with its own code search, for scale, security and lower maintenance. [5]

**Claude finds docs through a root `CLAUDE.md` of at most 100 lines that imports a generated index.** In one evaluation, run by a vendor on its own framework docs, an index inside the instruction file scored 100%. The same docs scored 53% when the agent had to go and look for them, and 79% when it was told to. [6] The check warns you when the index grows too large to import.

**The script generates the index, and CI fails when it's out of date.** A rule that says "keep the index updated" is advice. A check that fails when the index is out of date is check-backed.

**Every doc carries five fields: title, description, owner, status and last reviewed.** Status has three values. Each extra field would be one more thing to fill in and to check.

**An approved doc needs a named approver and at least one source.** One team at GitHub stores each fact with a pointer to its evidence and re-checks the pointer before using the fact. They reported a higher pull-request merge rate with the feature on. [7] The Linux kernel's rule for coding assistants puts responsibility on a named person. [8]

**A weekly job keeps one issue listing every doc nobody has confirmed in 180 days.** It puts the oldest dates in front of you every week.

**The check fails on invisible characters in docs and instruction files.** Researchers have shown that invisible characters in a shared instruction file can steer a coding assistant without showing up in review. [9]

## What to expect when you run it

**Expect the hook to stay quiet.** The map lists the check command and the settings allow Claude to run it, so Claude can run the check itself before the hook has to. The hook earns its place on the day a turn ends with broken docs, because that's when it warns you.

**Many old docs will show as stale on the first day.** When you add the required fields to existing docs, each one keeps the date of its last change, because adding fields isn't a review. Leave those docs stale until someone re-reads them.

**The docs check runs on every pull request, not just ones that touch docs.** A required check has to. If a workflow only runs when certain paths change, GitHub leaves its check pending on every other pull request and blocks the merge. [10]

**Unattended runs need the allowed commands passed in.** The allow rules in the committed settings let Claude run the check without asking, once you've accepted Claude Code's trust prompt for the folder. A scripted run doesn't show that prompt. In a folder you've never opened interactively, pass the same commands with `--allowedTools`. [11]

## What this chapter doesn't do

- **It can't tell you whether a doc is true.** It tells you which docs have an owner, a source and a recent review.
- **It enforces nothing until you turn the check on.** Your repository has to require the check on the default branch, with no bypass. Prompt 1 tells you which settings to change.
- **It doesn't cover secrets, tokens or which paths an agent may touch.** A later chapter does.
- **It doesn't find two docs that contradict each other.** Keeping one home for each fact makes that rarer.

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
