---
title: "Recipe 2: Decision records that say when they've gone stale"
description: "A prompt that adds architecture decision records with links between them, a check for broken links, and a list of records due for another look."
owner: charlcye
status: draft
last_reviewed: 2026-11-13
---

# Recipe 2: Decision records that say when they've gone stale

Write down why you chose a design and you can check the reasons later without relying on anyone's memory. The habit lasts when a record is cheap to write and when a script notices that one is out of date. This recipe sets up both.

## What you'll have

- A `docs/decisions/` folder with a template and numbered records.
- Each record says what it depends on, what it replaces, and when someone last confirmed it's still true.
- `scripts/decisions.py`, which fails when a record points at one that doesn't exist, when two records depend on each other in a loop, or when an accepted record depends on a superseded one.
- A `stale` command that lists records nobody has confirmed in 90 days, and the records that lean on them.
- A short prompt for turning a meeting transcript into a record.

## Before you start

This recipe stands alone. If you've already done [Recipe 1](00-single-source-of-truth/README.md), say so before you paste the prompt, because Recipe 1's check rejects fields it doesn't know and decision records carry their own. Ask the assistant to make the two checks agree.

## The prompt

```text
Add architecture decision records to this repo, with a check that keeps them consistent. Work in this repo and fit in with what exists.

Build these, in this order:

1. docs/decisions/TEMPLATE.md. Frontmatter fields:
   - id (adr-NNNN, matching the file name NNNN-short-slug.md)
   - title
   - status (one of: proposed, accepted, superseded)
   - date (YYYY-MM-DD, when it was decided)
   - last_verified (YYYY-MM-DD, when someone last confirmed it is still true)
   - depends_on (list of ids, may be empty)
   - supersedes (list of ids, may be empty)
   Body sections: Context, Decision, Options considered (each with why it lost), Consequences, How we'll know it was right.

2. docs/decisions/README.md: what a record is for, how to add one, and a table of all records (id, title, status, date).

3. scripts/decisions.py, standard library only, with two commands:
   - "check": exits 1 and prints "file: reason" for: a duplicate id; an id that doesn't match its file name; an unknown status; a bad date; depends_on or supersedes naming an id that doesn't exist; a dependency loop; an accepted record that depends on a superseded one; a record still marked accepted when an accepted record supersedes it (a proposed replacement doesn't count yet); a record missing from the README table. On success it writes docs/decisions/graph.json: every record with its fields, plus a reverse index of what depends on each record. graph.json is committed, and CI fails if the committed copy is out of date.
   - "stale --days N" (default 90): prints records whose last_verified is more than N days ago and, under each, the records that depend on it directly. Always exits 0. Give it a --today YYYY-MM-DD option for tests.
   Parse the frontmatter yourself; don't add a YAML dependency.

4. Tests that need no network: a passing set of three records, and one failing fixture for each rule in "check". Test "stale" with a fixed "today" so the test doesn't depend on the calendar.

5. CI: run the tests and "check" on pull requests touching docs/decisions/ or the script. Add a weekly scheduled job that runs "stale" and writes the result to the job summary. Use the CI system this repo already uses; if none, GitHub Actions with read-only permissions.

6. Write the first record yourself: adr-0001, the decision to keep decision records in this repo with this check. Fill in real options and real consequences.

7. In docs/decisions/README.md, add a section "Writing a record from a meeting" containing this prompt for people to reuse:
   "Read this transcript. For each design decision the group actually made, draft one record from docs/decisions/TEMPLATE.md. Quote the speaker, by name, for each reason. Leave status as proposed. List anything discussed but not decided under a heading 'Left open', and don't write records for those."

Finish by running the tests, then "check", then "stale", and show me all three outputs.
```

## What you should see

Three outputs: tests passing, `check` passing and reporting one record, and `stale` reporting nothing due.

## Check it yourself

1. Open `docs/decisions/0001-*.md` and change `depends_on: []` to `depends_on: [adr-9999]`.
2. Run `python3 scripts/decisions.py check`.
3. It should fail and say `adr-9999` doesn't exist.
4. Undo the change. Then set `last_verified` to a date a year ago and run `python3 scripts/decisions.py stale`. The record should be listed.
5. Undo that too.

## What this doesn't do

The CI job in this recipe runs only when decision records or the script change. Don't make it a required check, because GitHub leaves a skipped required check pending and blocks the merge.

It doesn't write the records for you, and it can't tell whether a record is true. It checks that every record has a row in the README table, but not that the row's title or status still matches the record. It lists the records to re-read, and it fails the check when a link between records breaks. Someone still has to open the record and update `last_verified`.

## Related files

- A record template: [`.claude/skills/architecture-gauntlet/assets/adr-template.md`](../../../.claude/skills/architecture-gauntlet/assets/adr-template.md)
- A design exercise that ends by writing a record: [`.claude/skills/architecture-gauntlet/`](../../../.claude/skills/architecture-gauntlet/)
