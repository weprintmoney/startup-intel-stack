---
title: "Terminus documents, prompt 2: see which docs your agents lean on"
description: "A prompt that adds a report of which instruction, agent and workflow files name which docs, and fails when one names a missing or archived document, or a draft terminus document."
owner: charlcye
status: draft
last_reviewed: 2026-11-14
---

# Prompt 2: See which docs your agents lean on

This prompt shows you which documents your agents depend on, by counting the files that name each one. Those files are your readers: a reader is any file that tells an agent or a job what to do and names a document. The reader report also fails when a reader names a document that's missing or archived, or a terminus document that's still a draft.

Counting replaces guessing at which docs matter most. The count can show a draft page that three readers rely on, or an approved document that no reader names. The [chapter overview](README.md) explains each choice built into the prompt.

## What you'll have

- `scripts/doc_readers.py`: the reader report, a table of each document with its status and its readers.
- A check, in CI, on what those files point at.
- Two lists in your weekly stale-docs issue: docs that may have earned a place among the terminus documents, and terminus documents nothing reads.
- One line per terminus document in `CLAUDE.md`, saying when to read it.
- `doc-readers.json`, where you can add or remove the files that count as readers.

## Before you start

Do [prompt 1](prompt-1-write-terminus-documents.md) first. Your terminus documents don't need to be approved yet; drafts are fine.

## The prompt

```text
Show me which documents my agents lean on, and stop them leaning on ones they shouldn't. Work in this repo and fit in with what exists. The repo already has docs/ with required fields, scripts/check_docs.py with tests and CI, a generated docs/INDEX.md, a root CLAUDE.md and terminus documents under docs/terminus/. If any of those are missing, stop and tell me.

The idea: a document matters as much as the number of things that read it. A "reader" is any file that tells an agent or a job what to do and names a document: CLAUDE.md files, files under .claude/, agent prompt files, CI workflow files and scripts. Count readers from the files, not from memory.

Build these, in this order:

1. scripts/doc_readers.py, standard library only.
   - It finds reader files: every CLAUDE.md and AGENTS.md, everything under .claude/, everything under an agents/ or prompts/ folder if one exists, CI workflow files, and files under scripts/. A "readers" list in a small config file at the repo root, doc-readers.json, can add or remove path patterns. Create that file with the defaults written out.
   - In each reader it finds references to files under docs/: Markdown links, import lines, and plain paths in text or code. A path that appears only inside docs/INDEX.md does not count, and docs/INDEX.md is not a reader.
   - With no arguments it prints a table, most-read first: document, status, number of readers, and the readers.
   - It exits 1 and prints "reader:line: reason" when a reader names a document that does not exist, a document whose status is archived, or a terminus document whose status is not approved. The last rule can be relaxed with "--allow-draft-terminus" so a new repo can pass while its documents are still drafts; print a warning for each instead.
   - "--candidates N" (default 3) lists documents outside docs/terminus/ that have N or more readers: these may have earned a place among the terminus documents. README.md files and the generated index are never candidates.
   - "--unread" lists terminus documents with no readers at all.
   - "--root PATH" points at another tree, for tests. Exit 2 with a clear message if docs/ is missing.

2. Tests that need no network: a passing tree; one failing fixture for each rule in step 1; a reference inside a fenced code block in a reader still counts; a reference that appears only in docs/INDEX.md does not; the candidates and unread lists. Build fixtures in temporary folders.

3. CI: run the tests and doc_readers.py on every pull request and every push to the default branch, in the same job as the docs check, not limited to certain paths. While any terminus document is still a draft, use "--allow-draft-terminus" and say so in a comment that tells me to remove the flag once they are approved.

4. The weekly job that keeps the "docs-stale" issue: add two sections to the issue body, "Candidates for terminus" and "Terminus documents nobody reads", from the two lists above. Keep its permissions as they are.

5. Make the terminus documents reachable. In CLAUDE.md, within its limit, add one line per terminus document saying when to read it. Don't import them. Add the reader report to the commands listed there and to the allowed commands in the project settings.

6. docs/terminus/README.md: add a short section, "How we know which documents matter", that says how to run the reader report and what to do with each list: a candidate is a prompt to ask whether its facts belong in a terminus document; an unread terminus document is either missing from the instructions or not needed.

Finish by running the tests, the docs check and the reader report, and show me all three outputs. Then tell me:
- every reader you found and which documents each names
- any reference that fails or warns today, and what I should do about each
- anything in this prompt you could not do, or did differently, and why
```

## What you should see

You should get passing tests, a passing docs check and the reader table. While any terminus document is a draft, run the report with `--allow-draft-terminus`. It then prints a warning for each reader that names a draft, and it still passes. Without the flag it fails.

## Check it yourself

Undo each step before you start the next.

1. Add this line to `CLAUDE.md`: "Read docs/product/shipping.md before quoting delivery times." Run `python3 scripts/doc_readers.py --allow-draft-terminus`. It should fail and say the file doesn't exist.
2. Change one document's `status` to `archived`, add its path to `CLAUDE.md`, and run the same command. It should fail and say the document is archived.
3. Run `python3 scripts/doc_readers.py --allow-draft-terminus --candidates 1`. It lists every document outside `docs/terminus/` that at least one reader names, apart from README files and the index. Run it again with `--candidates 3` to see only those with three or more readers, which may be none yet.
4. Start a new Claude Code session and ask for something one of your goals rules out. Claude should read the goals document, leave that part out and tell you which line rules it out.

If Claude goes ahead in step 4 without a word, look at the "when to read it" lines in `CLAUDE.md`, and make the one for goals say plainly which kinds of request it covers.

## Then keep it current

Once every terminus document is approved, remove `--allow-draft-terminus` from the CI job. The comment in the workflow reminds you.

When a doc appears as a candidate, ask whether its facts belong in a terminus document. The fix can be as small as moving two lines.

When a terminus document has no readers, either add the missing line to `CLAUDE.md` or archive the document.

## What this doesn't do

- **It only counts readers that name a document.** An agent that finds a document by searching goes uncounted.
- **It can't tell whether an agent followed a document it read.**
- **It fails on a document a script creates later.** If a script names a document it creates later, the reader report fails on it. Remove that script from the readers in `doc-readers.json`.
