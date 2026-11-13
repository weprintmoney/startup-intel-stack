---
title: "Cookbook"
description: "One capability at a time: a prompt you paste into your own repo, what you should have afterwards, and how to check it works."
owner: charlcye
status: draft
last_reviewed: 2026-11-13
---

# Cookbook

You don't have to adopt this whole template to get something out of it. Each recipe here adds one capability to a repo you already have. You paste a prompt into your coding assistant, it builds the thing, and you run a short check to see that it works.

## How to use a recipe

1. Open your coding assistant inside the repo you want to change.
2. Paste the prompt from the recipe.
3. Read what it built before you merge it.
4. Do the "Check it yourself" steps. They take a few minutes and they're the point: each one breaks something on purpose and confirms the new check notices.

Every recipe builds its checks before anything that acts on its own, and none of them needs a paid service to try.

## The recipes

Do them in this order. Each one stands alone, but later ones are more useful when the earlier ones exist.

| # | Recipe | What it adds | You'll know it works when |
|---|---|---|---|
| 1 | [One source of truth for your docs](01-docs-source-of-truth.md) | Required fields on every doc, an index, and a check for both | Deleting a doc's owner fails the check |
| 2 | [Decision records that say when they've gone stale](02-decision-records.md) | Numbered decision records, a link check, and a list of records due for another look | Pointing a record at one that doesn't exist fails the check |
| 3 | [A vetted-claims list with a retired-claims check](03-vetted-claims.md) | One list of what you can say, one of what you've stopped saying, and a check for the second | Pasting a retired phrase into your README fails the check |
| 4 | [A weekly signal digest](04-weekly-signal-digest.md) | A scheduled read of feeds you choose, opened as a pull request | A second run on the same day reports nothing new |

## Why this order

Agents repeat what they read. So the first three recipes make what they read trustworthy: documents with owners and dates, decisions with reasons, and claims with sources. The fourth is the first agent, and it's one that can only read and report.

The two papers in the [parent folder](../README.md) explain the reasoning at length.

## How the recipes are tested

Each recipe is run in an empty repo by an assistant that has seen nothing but the prompt. The recipe's "Tested" section records the date and what happened, including anything that failed. A recipe that hasn't been through that says so.
