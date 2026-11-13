---
title: "Recipe 1: One source of truth for your docs"
description: "A prompt that gives a repo a docs folder with required frontmatter, an index, and a check that fails when either drifts."
owner: charlcye
status: draft
last_reviewed: 2026-11-13
---

# Recipe 1: One source of truth for your docs

Every agent you add later will read your docs and trust them. This recipe makes the docs checkable first: each one says who owns it, what state it's in and when someone last looked at it, and a script fails the build when that information is missing.

## What you'll have

- A `docs/` folder where every document starts with the same five fields.
- An index in each folder's `README.md` that lists its documents.
- `scripts/check_docs.py`, which fails with the file name and the reason when a field is missing or a document isn't in its index.
- A CI job that runs the check on every pull request that touches `docs/`.

## Before you start

Open your coding assistant in the repo you want to add this to. Nothing else is needed. The script uses only the Python standard library.

## The prompt

```text
Set up a single source of truth for this project's documents. Work in this repo.

First look at what exists: is there a docs/ folder, a README, a CI setup, a test runner? Fit in with what's there. Don't move or rename existing files.

Build these, in this order:

1. A rule, written down in docs/README.md: every Markdown file under docs/ (except README.md files) starts with YAML frontmatter holding exactly these fields:
   - title
   - description (one line)
   - owner (a person's handle, or "unassigned")
   - status (one of: draft, review, approved, archived, stale)
   - last_reviewed (YYYY-MM-DD)
   Each folder under docs/ has a README.md that lists every document in that folder with a link.

2. scripts/check_docs.py, standard library only. It exits 1 and prints "path: reason" for each problem:
   - a doc with no frontmatter, a missing field, a field that isn't one of the five, an unknown status, or a date that isn't a real YYYY-MM-DD date
   - a folder under docs/ (docs/ itself included) that holds docs but has no README.md
   - a doc that its folder's README.md doesn't link to
   - a README.md link to a doc that doesn't exist
   It prints a warning, without failing, for any doc whose last_reviewed is more than 180 days old. Give it a --today YYYY-MM-DD option so tests don't depend on the calendar.
   Parse the frontmatter yourself; don't add a YAML dependency.

3. Tests for the script that need no network: one passing fixture tree, and one failing fixture for each rule above. Use the test runner this repo already has, or plain unittest if it has none.

4. A CI job that runs the tests and the script on pull requests touching docs/ or the script. Use the CI system this repo already uses; if it has none, add a GitHub Actions workflow with read-only permissions.

5. Bring existing docs into line: add frontmatter to any doc under docs/ that lacks it, with status "draft", today's date, and owner "unassigned". Take the title from the doc's first heading and write a one-line description from its content. Add missing index entries. If there are no docs yet, write one short real doc: docs/how-we-keep-docs.md, describing this rule.

Finish by running the tests and then the script, and show me both outputs. Then list every doc you marked "unassigned" so I can assign owners.
```

## What you should see

The assistant ends by showing the test run and a clean run of `check_docs.py`, followed by a list of documents that need an owner.

## Check it yourself

1. Open any document under `docs/` and delete its `owner:` line.
2. Run `python3 scripts/check_docs.py`.
3. It should exit with an error that names that file and says `owner` is missing.
4. Put the line back and run it again. It should pass.

If step 3 passes silently, the check isn't doing its job. Tell the assistant what you did and ask it to fix the script and add a test for that case.

## The working version in this repo

- The field rule: [`.claude/rules/doc-frontmatter-schema.md`](../../../.claude/rules/doc-frontmatter-schema.md)
- The index rule: [`.claude/rules/update-doc-index.md`](../../../.claude/rules/update-doc-index.md)
- The docs tree it governs: [`docs/`](../../)

## Tested

2026-11-13, in an empty repo holding a README, one source file and one doc, by an assistant given only the prompt.

- It built the rule, the script, 15 passing tests and a CI workflow.
- Deleting the `owner` line from a doc made the check fail with `docs/setup.md: missing field 'owner'`. Restoring it made the check pass.
- Not tested: the CI workflow was written but never run on a CI service.

After the run, the prompt was tightened to state choices the assistant had been left to make. Those lines describe what the tested build already does.
