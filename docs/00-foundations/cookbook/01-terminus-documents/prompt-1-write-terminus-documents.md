---
title: "Terminus documents, prompt 1: write your terminus documents"
description: "A prompt that interviews you and writes four short ground-truth documents in your own words, with checks that stop a half-finished one being approved."
owner: charlcye
status: draft
last_reviewed: 2026-11-14
---

# Prompt 1: Write your terminus documents

This prompt gets the facts that live only in your head into four short documents, in your own words. Claude asks the questions and does the typing. The prompt tells Claude never to mark a document approved, so that step stays with you.

Claude interviews you instead of handing you a template. A template makes you fill every box, including the ones an agent could have filled from your code and docs. The interview asks only for what no file contains. The [chapter overview](README.md) explains each choice built into the prompt.

## What you'll have

- `docs/terminus/company-brief.md`: what you make, who it's for, how you make money, and what you deliberately don't do.
- `docs/terminus/goals.md`: up to three priorities in order, how you'll know, and what you won't trade away.
- `docs/terminus/boundaries.md`: what an agent always does, asks you about first, and never does.
- `docs/terminus/glossary.md`: the words that mean something specific in your company, and the words you don't use.
- `docs/terminus/README.md` and a changelog.
- New checks in `scripts/check_docs.py`, and four new lines in `CLAUDE.md`.

## Before you start

Do both prompts in the [single source of truth](../00-single-source-of-truth/README.md) chapter first. Then set aside half an hour when you can answer questions, and have your GitHub handle ready.

## The prompt

```text
Help me write this company's terminus documents. Work in this repo and fit in with what exists. The repo already has docs/ with required fields, scripts/check_docs.py with tests and CI, a generated docs/INDEX.md and a root CLAUDE.md. If any of those are missing, stop and tell me.

A terminus document is one of the few short documents that everything else depends on: people and agents treat it as ground truth. Three rules for the whole build:
- I supply the facts. You ask, organise and draft. Never invent a fact about this company. Anything you take from existing files carries its source; anything nobody has confirmed ends with the tag "(unverified)".
- Short beats complete. A terminus document says only what an agent could not work out from the code or the other docs.
- Only I approve. You never set status to approved and never fill in approved_by.

Do these in order:

1. Read what exists: the README, everything under docs/, and the code layout. Then tell me, in a short list, what you already know for each of the four documents below and what you would have to ask me. Don't write any files yet.

2. Interview me, one document at a time, at most five questions per document, plain questions I can answer in a sentence each. If I don't answer, carry on with what the existing files support and mark the gaps. The four documents every company starts with:
   - docs/terminus/company-brief.md: what we make, who it is for, how we make money, and what we deliberately don't do.
   - docs/terminus/goals.md: at most three current priorities, in order. For each: how we'll know, and what we won't trade away to get it. Then a short list of things that matter less right now.
   - docs/terminus/boundaries.md: three lists for any agent working here: always do, ask me first, never do. Each line names a concrete action.
   - docs/terminus/glossary.md: the words that mean something specific here, one line each, and for each the word we don't use.

3. Ask me two yes-or-no questions: will agents work on product code, and will agents write to customers or prospects? Create nothing for a "no". For each "yes", tell me which further documents that work will need (product: architecture and invariants, security and data handling; customers: positioning and customer profile, voice, approved claims) and add them to a list in docs/terminus/README.md under "Not written yet". Don't draft them now.

4. Write the four documents. Each has the repo's required fields with status "draft" and a sources list naming the files you drew on. Each is at most 150 lines. Where I gave you an answer in the interview, write it as I said it and put "(owner, <today's date>)" next to it. The rules in this prompt are instructions for this build, not answers from me; don't record them as mine. Set owner to my handle if I give you one, and to "unassigned" if I don't. Where you inferred something from a file, say which file. Where there is a gap, write the question as an open item at the end under "Open questions"; don't fill it with a guess.

5. docs/terminus/README.md: what a terminus document is, the list of them with one line each, the "Not written yet" list, and the rule for adding one: when I have corrected an agent twice for the same missing fact, propose a new terminus document or a new line in an existing one, and let me decide. Also docs/terminus/CHANGELOG.md with one dated line for today. The changelog is a plain list with no required fields and is left out of the index; teach the check that.

6. Extend scripts/check_docs.py, with tests, for files under docs/terminus/ (README.md and CHANGELOG.md excepted):
   - fail if a document is over 150 lines
   - fail if an approved document has a line that ends with the tag "(unverified)", contains "TBD" or "TODO" outside quotation marks and code, or has list items under an "Open questions" heading
   - warn when last_reviewed is more than 90 days old, in place of the 180-day warning, and list these first in "--stale"
   - with "--changed-against REF", compare the working tree with REF, uncommitted files included, and fail if any terminus document differs from REF and docs/terminus/CHANGELOG.md does not; use this in the pull-request CI job against the base branch

7. In CLAUDE.md, add to the map one line for docs/terminus/, and add these three lines to the "Never" list or next to it, keeping the file within its limit:
   - when what I ask for conflicts with a line in a terminus document, do the rest, leave that part out, quote the line and ask me
   - never edit a file under docs/terminus/ unless I asked for that change in this conversation; propose it instead
   - when a document describes how the code behaves and the code behaves differently, the code is the fact: tell me the document is out of date. When a terminus document states a decision or a rule and the code breaks it, the document stands: tell me the code is wrong. Either way, tell me before you act on it.

Finish by regenerating the index, running the tests and the check, and showing me both outputs. Then give me:
- for each of the four documents, the lines that came from me, the lines that came from files, and the open questions
- any place where my answers disagree with each other or with the glossary
- what I need to do to approve a document, as exact commands
- anything in this prompt you could not do, or did differently, and why
```

## What you should see

Claude starts with a short list, for each document, of what it already knows from your files and what it would have to ask. Then come the questions, one document at a time, and two yes-or-no questions about the work your agents will do. If you'd rather answer everything at once, say so.

Once you've answered, you get four drafts, passing tests and a passing check. Claude's closing report sorts each document's lines by where they came from, lists the open questions, shows where your answers disagree and gives the exact commands to approve a document. Read its last section with care: it says what Claude couldn't do or did differently.

## Check it yourself

Steps 2 and 3 are tests, so undo their edits when you're done, but keep the commit. Step 4 is a real approval, so keep that too.

1. Open `docs/terminus/goals.md`. Every line you gave should carry "(owner, " and the date of the interview. Every other statement of fact should name the file it came from or end with "(unverified)".
2. Pick a document that still has an open question, or add one under "Open questions". Set its `status` to `approved` and add `approved_by` with your handle. Run `python3 scripts/check_docs.py`. It should fail and point at the open question. It will also report the index as out of date, because the index records each status.
3. Commit everything the prompt built. Then add a line to any terminus document, leave the changelog alone, and run `python3 scripts/check_docs.py --changed-against HEAD`. It should fail and ask for a changelog line.
4. Answer the open questions in one document, and confirm or remove every line that ends with "(unverified)". Then approve it with the commands Claude gave you, which include a changelog line. The check should pass.

If step 1 turns up a line you didn't say, tell Claude which line it is and ask where it came from.

## Then finish the set

Work through the list of disagreements. Settle each one and tell Claude which answer stands.

Approve each document once its open questions are gone. An agent can read a draft in the meantime, and prompt 2 warns you about every reader that names one.

From then on, when you correct an agent twice for the same missing fact, ask Claude to propose a line for the right document.

## What this doesn't do

- **It can't tell whether your answers are right.** Read each document before you approve it.
- **It doesn't restrain an agent.** The documents advise it. A rule that needs enforcing belongs in a hook or a check.
- **It leaves the product and go-to-market documents unwritten.** If you told Claude that agents will do that work, they're listed in `docs/terminus/README.md` under "Not written yet".
