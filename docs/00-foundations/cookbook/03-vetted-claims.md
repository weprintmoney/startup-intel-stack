---
title: "Recipe 3: A vetted-claims list with a retired-claims check"
description: "A prompt that adds one list of what you can say about your product, one list of what you've stopped saying, and a check that fails when a retired claim shows up."
owner: charlcye
status: draft
last_reviewed: 2026-11-13
---

# Recipe 3: A vetted-claims list with a retired-claims check

Products change faster than the sentences written about them. A number that was true in spring stays on the website through autumn, and an agent that drafts copy will repeat whatever it finds. This recipe gives you one place that says what you can claim today, and a check that fails when a retired claim appears, word for word, in the folders you scan.

Retired claims are the hard ones to catch by reading, because most of them used to be true.

## What you'll have

- `docs/claims-vetted.md` with two tables: claims you can make, each with a source and an expiry date, and claims you've retired, each with what to say now.
- `scripts/check_retired_claims.py`, which reads the retired phrases from that table and fails when one appears in the files you point it at.
- A CI job that runs it on every pull request.

The retired phrases live in one place. The script reads them from the table each time it runs, so there's no second copy inside the script to keep in step.

## Before you start

Decide which folders hold words a customer might read: a website, a README, sales templates, docs. The assistant picks the folders by looking at your repo and reports what it chose, so check its list against yours.

If you've already done [Recipe 1](00-single-source-of-truth/README.md), say so before you paste the prompt. Recipe 1's check expects every file under `docs/` to start with its required fields, so ask the assistant to make the two checks agree.

## The prompt

```text
Add a vetted-claims list and a retired-claims check to this repo. Work in this repo and fit in with what exists.

Build these, in this order:

1. docs/claims-vetted.md with two Markdown tables under fixed headings:
   "## Claims we can make" with columns: Claim | Source | Last verified | Expires
   "## Retired claims" with columns: Phrase | Retired on | Why | Say instead
   Above the tables, three sentences on how to use the file: copy claims from the first table word for word; never use a phrase from the second; add a row to the second table whenever a claim stops being true.

2. claims-check.json at the repo root: "scan" (list of path globs to check) and "exempt" (list of path globs to skip). Look at this repo and fill "scan" with the places customer-facing words live (for example README.md, docs/, site or marketing folders, email templates). Always exempt docs/claims-vetted.md, the tests, and changelogs. In a glob, * stays within one folder and ** crosses folders.

3. scripts/check_retired_claims.py, standard library only:
   - Reads the phrases from the "Retired claims" table in docs/claims-vetted.md at run time. The script contains no phrases of its own.
   - Scans the files matched by "scan" minus "exempt". Matching ignores case and treats any run of spaces or line breaks as one space.
   - For each hit prints "path:line: retired claim '<phrase>'. Say instead: <say instead>" and exits 1. The line is where the phrase starts.
   - Skips any line containing the comment <!-- retired-claims: ignore --> so a page can discuss an old claim on purpose.
   - Separately prints a warning, without failing, for each row in "Claims we can make" whose Expires date has passed. Warnings go to stderr.
   - Exits 2 with a clear message if the claims file or either table is missing, so a broken file can never pass silently.
   - "--all" scans everything in scope; with file paths as arguments it scans only those, still skipping exempt paths. "--root PATH" points it at another tree, for tests.

4. Tests that need no network: a clean tree that passes; a hit; a hit split across a line break; a hit in different capitals; an ignored line; an exempt path; an expired claim (warns, exits 0); a missing table (exits 2).

5. CI: run the tests and "check_retired_claims.py --all" on every pull request. Use the CI system this repo already uses; if none, GitHub Actions with read-only permissions.

6. Seed the tables. Read the README and any marketing or docs pages. Put up to five factual claims you find into "Claims we can make", with Source left as "NEEDS SOURCE", Last verified as "Not yet verified", and Expires 90 days from today. Don't invent claims and don't invent sources. Put one row in "Retired claims" that is plainly an example (phrase "EXAMPLE retired phrase, replace me") so the format is visible.

Finish by running the tests and then "--all", and show me both outputs. Then tell me: which paths you chose to scan, and which claims need a source from me.
```

## What you should see

Tests passing, a clean `--all` run, the list of paths being scanned, and a list of claims waiting for a source from you.

## Check it yourself

1. Add a real row to the "Retired claims" table: a phrase you used to say, and what to say now.
2. Paste that phrase into your README, in different capitals.
3. Run `python3 scripts/check_retired_claims.py --all`.
4. It should fail, name the README and the line, and print your "say instead" text.
5. Remove the phrase from the README. It should pass again.

## Then keep it honest

- Fill in a source for every claim marked `NEEDS SOURCE`, or delete the claim.
- When something stops being true, move it to the retired table the same day.
- Point any agent that writes copy at `docs/claims-vetted.md` and tell it to use those claims word for word.

## What this doesn't do

It matches retired phrases word for word, so a paraphrase of an old claim passes. It can't tell whether a claim in the first table is true. It warns when a claim's expiry date has passed, and someone still has to check the source.

## Related files

- An example claims file: [`docs/04-marketing/content-ops/claims-vetted.md`](../../04-marketing/content-ops/claims-vetted.md)
- A gate that checks agent-written specs against it: [`examples/agent-ops-skeleton/agents/claim-verifier/`](../../../examples/agent-ops-skeleton/agents/claim-verifier/)
