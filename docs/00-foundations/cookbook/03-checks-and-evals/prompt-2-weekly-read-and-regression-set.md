---
title: "Checks and evals, prompt 2: the weekly read and the regression set"
description: "A prompt that builds a weekly review sheet of real agent outputs for you to label, turns failures a script can recognise into cases, and re-runs them on every pull request that changes an agent."
owner: charlcye
status: draft
last_reviewed: 2026-11-17
---

# Prompt 2: The weekly read and the regression set

This prompt sets up two habits and the scripts behind them. Once a week you read a sample of real outputs and label each one pass or fail, with a reason. Each failure a script can tell apart becomes a case, and an agent's cases run again on every pull request that changes it.

Claude builds the sheet and the commands, and never labels for you. You decide whether an output is good. The prompt says so in its first paragraph and again in its rules, and its scripts refuse a sheet they can't read as your verdicts. The [chapter overview](README.md#an-output-from-start-to-finish) follows one failure from the sheet to a case.

## What you'll have

- **`scripts/review_sample.py`**, which builds a review sheet of up to 30 runs you haven't labelled, plus any run that failed a check or hit a limit. With `--save`, it appends your verdicts to `evals/<agent>/labels.jsonl`.
- **`scripts/add_case.py`**, which turns a run you labelled fail into a case with a check a script can grade.
- **`scripts/run_regression.py`**, which runs an agent's cases. `--trials K` runs each case K times, and `--changed BASE` runs only the agents that changed since a commit.
- **A `regression` job** in CI, on every pull request.
- **A `weekly-read` issue**, kept open by a scheduled job while records are waiting, with the two commands to run.
- **`docs/reviews/`**, with a template for a written review after harm, and a docs check that an approved review names the case or code check that was added.

## Before you start

Do [prompt 1](prompt-1-run-and-check-agents.md) first. This prompt reads the run records its runner writes.

The `regression` job needs the model key. The prompt names the secret it reads and adds it to your secrets list.

## The prompt

```text
Set up a weekly read of what my agents produce, and a small set of past failures that is re-run whenever an agent changes. Work in this repo and fit in with what exists. The repo already has agents.json, scripts/run_agent.py (which writes run records), scripts/check_agent_output.py, docs/agents.md, scripts/check_workflows.py and CI. If any of those are missing, stop and tell me. I am the only person working on this repo, and I am the one who decides whether an output is good.

Some words, so we mean the same thing:
- A "label" is my verdict on one run record: pass or fail, with one line saying why.
- A "case" is one input an agent once got wrong, saved with a way for a script to tell right from wrong.
- An agent's "regression set" is its cases. It should pass nearly every time. It tells me an old failure has come back. It says nothing about failures I haven't seen.

Three rules for the whole build:
- I label. Never write a label for me, never guess one, and never mark a case as passing by changing what it expects.
- A case is graded by code. If a failure can't be told apart by a script, say so and leave it for a judge, which is a later job.
- No test may call a model or the network. Tests use the fake CLI that run_agent.py's tests use.

Build these, in this order:

1. scripts/review_sample.py, standard library only. Given a folder of run records, it picks up to N (default 30) that I haven't labelled, spread across agents and favouring the newest. Any run that failed a check or hit a limit goes on the sheet as well, even past N. A record's id is its file name without ".json". It writes a review sheet, review/YYYY-MM-DD.md: for each record the agent, the date, the input, the output, and an empty "verdict:" and "why:" line. "review_sample.py --save review/YYYY-MM-DD.md" reads my filled-in sheet and appends each verdict to evals/<agent>/labels.jsonl with the record's id, the date, the prompt hash and the model from the record, my verdict and my reason. A record I left empty is skipped and comes up again next time. It refuses a sheet that has a verdict other than pass or fail, or a fail with no reason, and saves nothing from it. It prints how many I labelled and the fail rate per agent.

2. scripts/add_case.py, standard library only. "add_case.py RECORD_ID --expect JSON" turns a record I labelled fail into evals/<agent>/cases/<short-name>.json: the input, my reason, and an "expect" block a script can grade: a field that must equal a value, phrases that must or must not appear, or a path that must or must not be changed. It shows me the case and writes it only with "--yes". It refuses an expect block that passes on the very output I failed, and it never writes over a case. When I ask you in a session to make a case from a failed record, propose the expect block from my reason and show it to me first; if my reason can't be expressed as a code check, say so and write nothing.

3. scripts/run_regression.py, standard library only. "run_regression.py AGENT" runs every case for that agent through run_agent.py and grades each against its expect block. "--trials K" (default 1) runs each case K times; a case passes only if every trial passes, and the report shows how many of K passed. It prints one line per case and a total, writes the results to a JSON file, and exits 1 if any case failed, 2 if a run could not be completed. "--changed BASE" works out which agents changed since a commit (their prompt file, their entry in agents.json, or their cases) and runs only those; a change to scripts/run_agent.py counts as a change to every agent. With nothing changed it says so and exits 0. It lists any case whose expect block was edited or deleted since that commit, so I see it in the pull request.

4. Tests that need no network or model: the sample favours failed runs and skips labelled ones; a bad sheet is refused whole; a label is appended with the right fields; add_case writes nothing without "--yes"; each kind of expect block passing and failing; all-of-K grading; "--changed" picking the right agents for a prompt change, a model change and a case change.

5. CI, in a job of its own named "regression": on every pull request, run "run_regression.py --changed" against the base branch. The job must always run and report, so it can be a required check: don't limit it by paths, and don't let it be skipped. It needs the model key, so say which secret it reads and add it to the secrets list. Give it the limits every agent job has. Some pull requests get no secrets, such as one from a fork. If no agent changed, the job passes without the key. If one did and there is no key, make the job fail with a clear message, not pass.

6. A weekly reminder. A scheduled job counts the run records from the last seven days' agent runs and the labels saved in that time, and keeps one issue open, "weekly-read", that says how many records are waiting and gives the two commands to run. It closes the issue when nothing is waiting. It has no agent in it. Tell me how it gets the records, and what I must do on my laptop to fetch them.

7. A written review after harm. Add docs/reviews/README.md and docs/reviews/TEMPLATE.md, with the repo's required fields: what happened and who it reached, what changed beforehand (prompt, model, input or code), why the checks missed it, and which case or code check was added so it can't pass unnoticed again. Extend the docs check so that a review with status "approved" must name a file under evals/ or scripts/ that exists. Add a line to docs/agents.md's generated page: each agent's number of cases, the date of its last label and its last review.

8. In CLAUDE.md, within its limit, add one line: a change to an agent's prompt or model runs its regression set, and a failed output becomes a case before the prompt is fixed.

Finish by running all the tests and checks and showing me the outputs. Then walk me through one round on real data, without labelling for me: run one agent three times on inputs I would recognise, build the review sheet, and stop. Show me the sheet and tell me exactly what to type into it and which commands to run next.

Then tell me:
- what each agent's regression set holds now (it may be empty, and that is fine)
- what the weekly read and the regression set cannot catch
- how long one weekly read should take me, and what to do in a week I skip
- every question that needs my answer
- anything in this prompt you could not do, or did differently, and why
```

## What you should see

First, passing tests and checks. Then one round on real data: Claude runs one agent three times on inputs you'd recognise, builds the review sheet and stops. It shows you the sheet and tells you exactly what to type into it and which commands to run next.

The report says what each agent's regression set holds. On the first day that's probably nothing, and that's fine. It also says what the weekly read and the regression set can't catch, how long a read should take, and what to do in a week you skip.

## Check it yourself

Script names and flags below are whatever Claude built. If a command differs, ask Claude for the equivalent.

1. In the review sheet, type `maybe` after one `verdict:`. Run `python3 scripts/review_sample.py --save review/<date>.md`. It should refuse the sheet and save nothing. Fix the verdict.
2. Label one record `fail` with a reason and save. Run `python3 scripts/add_case.py <record id> --expect '<json>'` without `--yes`. It should show you the case and write nothing.
3. Give it an expect block that the failed output already satisfies. It should refuse and say the block can't tell right from wrong.
4. Keep this one. Write one real case with `--yes`, then run `python3 scripts/run_regression.py <agent>`.

If any step passes when it should fail, tell Claude what you did and ask it to fix the script and add a test.

## Then finish the job

- **Do the first weekly read.** Type `pass` or `fail` after each `verdict:`, and one line after `why:` for every fail. At the cap of 30 records, a read takes roughly 30 to 60 minutes, as an estimate. If you skip a week, nothing is lost: unlabelled records come up again.
- **Make `regression` a required check** on the default branch.
- **Decide how many trials CI runs.** One trial of an agent can pass by luck.
- **Decide whether `regression` gets its own model key**, with its own spend limit.

## What this doesn't do

- **The weekly read only sees what you sample.** Past 30 records it favours the newest. It only sees runs whose records it can fetch, and build artifacts expire, after 90 days by default on GitHub.
- **A phrase check is loose.** A case that expects a doc's path to appear passes on any output that mentions the path, including one that says the doc doesn't exist. Read a case's first few results yourself.
- **One trial of an agent can pass by luck.** Use `--trials`.
- **The regression set says nothing about failures you haven't seen.**
- **An edited or deleted case is listed on the pull request, not blocked.** No agent may change `evals/`, but a person can.
- **The review rule checks that an approved review names a real file.** It doesn't check that the file is the right fix.
