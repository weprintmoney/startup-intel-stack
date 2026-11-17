---
title: "Checks and evals, prompt 3: a judge with its own test"
description: "A prompt that builds one model judge for one recurring failure code can't check, measures it against your held-back labels, and won't let it run until it has been measured."
owner: charlcye
status: draft
last_reviewed: 2026-11-17
---

# Prompt 3: A judge with its own test

This prompt builds one model judge for one failure that code can't check, and it won't let the judge run until the judge has been tested against your own labels. It starts by reading the reasons in your labels, and it may tell you that you don't need a judge yet. That's a good outcome.

The judge advises. Its verdict appears beside yours in the weekly read, after you've given yours, and it never blocks a merge or changes an agent's output. The [chapter overview](README.md#why-the-prompts-are-built-this-way) explains why the judge is measured with two rates rather than one.

## What you'll have

Only if your labels show a recurring failure that code can't check:

- **A judge file under `evals/<agent>/judges/`**, with one question, what counts as pass and as fail, when to answer "unknown", and three to six of your labelled examples.
- **`scripts/judge.py`**, which runs the judge on one run record with no tools, a turn limit and a spending limit. It exits 3 and runs nothing unless a validation is on file for this exact judge file and model.
- **`scripts/validate_judge.py`**, which measures the judge on the half of your labels held back from writing it, and writes the result beside the judge file.
- **The judge's verdict beside yours in the weekly read**, with how often you and the judge agreed that week.
- **A judges table in `docs/agents.md`**: each judge's question, its model, and the date and two rates of its last validation, or "not validated" if the file or the model has changed since.

## Before you start

Do prompts [1](prompt-1-run-and-check-agents.md) and [2](prompt-2-weekly-read-and-regression-set.md) first, and keep labelling until the same failure has come up many times. The validator wants at least 20 labels in the held-back half, with at least 8 fails among them, and only half your labels go there.

Claude will ask which model the judge should use. The sources disagree on whether a judge should be a different model from the one that wrote the output, so the prompt has Claude quote what the Claude documentation recommends before you choose.

## The prompt

```text
Build one model judge for one failure that code can't check, and don't let it run until it has been tested against my own labels. Work in this repo and fit in with what exists. The repo already has agents.json, scripts/run_agent.py, run records, evals/<agent>/labels.jsonl with my pass/fail labels and reasons, scripts/run_regression.py and CI. If any of those are missing, stop and tell me.

Start by reading my labels, and only the reasons in them: don't open the run records yet. Tell me, for each agent, the failures I gave reasons for, grouped by reason, with a count. For each group say whether a script could check it. If every group could be checked by code, or no group that needs judgement has come up more than a few times, tell me I don't need a judge yet and stop. Otherwise propose the one failure that most deserves a judge, list which of my reasons count as that failure, and ask me to confirm both.

Some words, so we mean the same thing:
- A "judge" is a prompt that asks a model one yes-or-no question about one output.
- Its "catch rate" is the share of outputs I labelled fail that it also fails. Its "pass rate on good work" is the share I labelled pass that it also passes. A judge needs both numbers; overall agreement hides a judge that passes everything.

Four rules for the whole build:
- One judge asks one question. Its answer is "pass", "fail" or "unknown", with one sentence of reason. No scores.
- My labels are the truth the judge is measured against. Never change a label to match the judge.
- The judge advises. It never blocks a merge and never changes an agent's output.
- No test may call a model or the network. Tests use a fake CLI.

Build these, in this order:

1. evals/<agent>/judges/<name>.md: the question, what counts as pass and as fail in plain words, when to answer "unknown", and three to six of my labelled examples with my reasons, taken only from the half of the labels set aside for writing the judge (step 3). Add the judge to the agent's entry in agents.json with the reasons that count as its failure and a full model name that the model documentation says maps to one fixed version. Ask me which model; say what the Claude documentation recommends about judging with the same model that wrote the output, and quote it.

2. scripts/judge.py, standard library only. "judge.py AGENT NAME RECORD" runs the judge on one run record through the Claude Code CLI with no tools, a turn limit and a spending limit, and prints the verdict and reason as JSON. It treats an answer it can't parse as "unknown". It records the judge's model and a hash of the judge file with every verdict. It exits 3 and runs nothing if there is no validation on file for this exact judge file and model (step 3).

3. scripts/validate_judge.py, standard library only.
   - It splits my labels in two by a hash of the record id, so the split never changes: one half for writing the judge, one half held back for the test. A fail whose reason isn't one of the judge's is left out and reported, never counted as a pass. Make the split before you read any record, and read only records from the writing half.
   - It runs the judge on the held-back half and prints the catch rate and the pass rate on good work, each as a fraction with its counts, and lists every record where the judge and I disagree, with both reasons. An "unknown" counts against whichever rate that record belongs to. It warns when outputs in the held-back half repeat outputs in the writing half, because that flatters both rates.
   - It writes evals/<agent>/judges/<name>.validation.json: the date, the judge's model, the hash of the judge file, the counts and the two rates.
   - It refuses to write a validation, and says how many more labels are needed, if the held-back half has fewer than 20 labels or fewer than 8 fails. With "--accept-small" it writes one marked "small sample", and judge.py prints that warning on every verdict.
   - It never edits the judge file. Improving the judge is my decision after I read the disagreements.

4. Tests that need no network or model: the split is stable and never puts one record in both halves; the two rates are right on a made-up set, including a judge that passes everything; too few labels is refused; judge.py refuses without a validation, and after the judge file or the model changes; an unparseable answer becomes "unknown".

5. Where it runs. Add the judge to the weekly read: review_sample.py shows the judge's verdict beside each record once I have given mine, never before, and reports each week how often the judge and I agreed. If agreement on a week's labels falls well below the validation rates, say so in the "weekly-read" issue. Propose what "well below" means and ask me. Don't add the judge to any required check.

6. In docs/agents.md's generated page, show each judge: its question, its model, the date and the two rates of its last validation, and "not validated" if the file or model has changed since.

Finish by running all the tests and showing me the output. Then run validate_judge.py for real and show me the two rates and every disagreement. Don't tune the judge to raise them. If the rates are poor, say so plainly and tell me what you'd try.

Then tell me:
- whether I should use this judge, in one sentence, and why
- what it cost to validate, and what one verdict costs
- what the judge cannot tell me
- when I must validate it again
- anything in this prompt you could not do, or did differently, and why
```

## What you should see

First, a count of your failure reasons for each agent, grouped by reason, each marked with whether a script could check it. Then one of two things. Claude tells you that you don't need a judge yet and stops, or it proposes the one failure that most deserves a judge, lists the reasons that count as that failure, and asks you to confirm both.

After the build you get passing tests and one real validation: the catch rate and the pass rate on good work, each as a fraction with its counts, and every record where the judge and you disagreed, with both reasons. Claude doesn't tune the judge to raise the rates. If they're poor, it says so and tells you what it would try.

The report ends with whether to use the judge and why, what the validation cost and what one verdict costs, what the judge can't tell you, and when to validate it again.

## Check it yourself

Script names and flags below are whatever Claude built. If a command differs, ask Claude for the equivalent.

1. Add a line to the judge file. Run `python3 scripts/judge.py <agent> <judge> <record file>`. It should exit 3 and say the judge file has changed since it was validated. Undo.
2. Change the judge's model in `agents.json` and run the same command. It should refuse in the same way. Undo.
3. Read every disagreement the validation listed, with both reasons. Decide for each one whether the judge or your label needs to change. Never change a label just to match the judge.

## Then finish the job

- **Read the disagreements.** Decide for each one whether the judge or your label needs to change.
- **Decide whether to use the judge.** Nobody has shown an agreement level at which a judge is good enough, so this is your call.
- **If the sample was small, keep labelling and validate again.** A judge that scores 100% on a small or repetitive held-back set hasn't been shown to be perfect.

## What this doesn't do

- **The judge reads the output text only.** It can't tell whether the agent really did what it says, or whether the facts are right.
- **It answers one question.** Other failures pass it by design.
- **Its rates describe the labels you had.** Failures worded unlike those may get through.
- **A validation goes stale.** Validate again after any change to the judge file or its model, which the script enforces, when the weekly issue says agreement fell, and when the agent's prompt, model or tools change.
