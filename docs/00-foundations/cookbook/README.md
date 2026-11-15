---
title: "Cookbook"
description: "One capability at a time: a prompt you paste into your own repo, what you should have afterwards, and how to check it works."
owner: charlcye
status: draft
last_reviewed: 2026-11-14
---

# Cookbook

Each recipe here adds one capability to a repo you already have, and none of them needs the rest of this repo. You paste a prompt into your coding assistant, it builds the thing, and you run a short check to see that it works.

## How to use a recipe

1. Open your coding assistant inside the repo you want to change.
2. Paste the prompt from the recipe.
3. Read what it built before you merge it.
4. Do the "Check it yourself" steps. They take a few minutes. Most of them break something on purpose and confirm the new check notices.

Every recipe builds its checks before anything that acts on its own. You can try all six without signing up for another service. Recipe 6 adds a model-written summary if you give it an API key.

## The recipes

Do them in this order. Recipe 2 builds on recipe 1, and recipe 3 builds on both. The others stand alone, and they're more useful when the earlier ones exist.

| # | Recipe | What it adds | You'll know it works when |
|---|---|---|---|
| 1 | [Single source of truth](00-single-source-of-truth/README.md) (two prompts) | Checked fields on every doc, a generated index, sources and an approver on approved docs, a stale list, and the wiring for Claude Code | Deleting a doc's owner fails the check |
| 2 | [Terminus documents](01-terminus-documents/README.md) (two prompts) | Four short ground-truth documents in your own words, checks on approving them, and a report of which docs your agents lean on | Approving a document with an open question fails the check |
| 3 | [Permissions and secrets](02-permissions-and-secrets/README.md) (two prompts) | A check on what every workflow can reach, a names-only list of secrets, a pause switch that fails closed, and the Claude Code sandbox | Giving a workflow write access at the top level fails the check |
| 4 | [Decision records that say when they've gone stale](02-decision-records.md) | Numbered decision records, a link check, and a list of records due for another look | Pointing a record at one that doesn't exist fails the check |
| 5 | [A vetted-claims list with a retired-claims check](03-vetted-claims.md) | One list of what you can say, one of what you've stopped saying, and a check for the second | Pasting a retired phrase into your README fails the check |
| 6 | [A weekly signal digest](04-weekly-signal-digest.md) | A scheduled read of feeds you choose, opened as a pull request | A second run on the same day reports nothing new |

Recipes 1 to 3 are full chapters. Each explains the choices built into its prompts and links to the sources behind them.

## Why this order

Agents repeat what they read. So recipes 1, 2, 4 and 5 make what they read checkable. Documents get owners and dates, decisions get reasons, and claims get sources. Recipe 3 limits what your agents and workflows can reach. The sixth is the first scheduled agent, and it's one that can only read and report.

The two papers in the [parent folder](../README.md) explain the reasoning at length.

## If a check doesn't catch the break

Run the "Check it yourself" steps after every recipe. If a step passes when it should fail, tell your assistant what you did and ask it to fix the script and add a test for that case.
