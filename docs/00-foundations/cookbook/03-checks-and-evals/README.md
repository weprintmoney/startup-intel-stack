---
title: "Checks and evals"
description: "How to check what your agents produce: code checks on every run, a weekly read of real outputs, past failures re-run on every change, and a model judge only once it has been tested against your own labels."
owner: charlcye
status: draft
last_reviewed: 2026-11-17
---

# Checks and evals

In this chapter you build the checks on what your agents produce. Every agent runs through one script that enforces its limits and records each run, and code checks every output it can. Once a week you read a sample of real outputs and mark each one pass or fail. A failure a script can recognise becomes a case that runs again whenever the agent changes. A model judges an output last, only for a failure code can't check, and only after it has been measured against your own labels.

Do this once your agents run unattended. Nobody watches an agent while it runs, and a check that depends on your attention stops working the week you're busy. Put every check you can into a script, and save your attention for what a script can't do.

The chapter assumes you're the only person who owns the system and that you use Claude Code with GitHub Actions. It describes the tools as they were in November 2026, and it builds on the earlier chapters: [single source of truth](../00-single-source-of-truth/README.md), [terminus documents](../01-terminus-documents/README.md) and [permissions and secrets](../02-permissions-and-secrets/README.md).

## The prompts

Run them in order. Each prompt expects the files the one before it creates.

1. **[Run and check your agents](prompt-1-run-and-check-agents.md).** Adds one runner that every agent starts through, with a pinned model, limits on turns, dollars and minutes, and a record of every run, plus code checks on what each agent produces and changes. To test it, change an agent's model to an alias such as `sonnet`: the agents check should fail.
2. **[The weekly read and the regression set](prompt-2-weekly-read-and-regression-set.md).** Adds a weekly review sheet, a script that turns a failure into a case, and a `regression` job on every pull request. To test it, type a verdict other than pass or fail into the sheet: the whole sheet should be refused and nothing saved.
3. **[A judge with its own test](prompt-3-a-judge-with-its-own-test.md).** Builds one model judge for one failure code can't check, if your labels show that failure coming back, and measures it on labels it hasn't seen. To test it, change one line of the judge file: the judge should refuse to run until you validate it again.

The rest of this page explains how the checks fit together, so that when you find a failure you know which check should have caught it.

## Who decides whether an output is good

An **agent**, in this chapter, is a job that runs the Claude Code CLI with a prompt and no person watching. Each run leaves a **run record**: what the agent was given, what it produced and what it cost. Three things can judge a run record, and the prompts use them in this order.

A **code check** is a test a script can decide. It needs no model and gives the same answer every time. Anthropic's guide to building evaluations calls code-based grading "Fastest and most reliable, extremely scalable, but also lacks nuance". [1]

**You** decide what code can't. A **label** is your verdict on one run record: pass or fail, with one line saying why. One FAQ on evals advises starting with one person whose judgement is final, and with "error analysis, not infrastructure": "Spend 30 minutes manually reviewing 20-50 LLM outputs". [2]

A **judge** is a prompt that asks a model one yes-or-no question about one output. It comes last. The FAQ advises building expensive evaluators only "for problems you'll iterate on repeatedly". [2] Anthropic's guide says of grading with a model: "Test to ensure reliability first, then scale." [1]

Think of a restaurant kitchen. The fridge thermometer is the code check: it reads the same every time, and it can't tell you whether the soup is good. The chef tasting plates is your weekly read. A cook may taste for her, but only after she has compared his calls with her own on plates she has already tasted. The comparison has one limit. A cook brings years of tasting to the job. A judge knows only its question and your examples, and its rates describe only the labels you measured it on.

When you label a run fail and a script can tell the failure apart, you save it as a **case**: the input, your reason, and a check a script can grade. An agent's cases make up its **regression set**. Anthropic's write-up on agent evals says regression evals "should have a nearly 100% pass rate", and that "20-50 simple tasks drawn from real failures is a great start." [3] A regression set tells you an old failure has come back. It says nothing about failures you haven't seen, so the weekly read carries on as the set grows.

Passing tests isn't the same as good work. In one study, four maintainers of three open-source projects reviewed 296 agent pull requests that passed the tests. The study estimates that roughly half of test-passing pull requests would not be merged. [4]

## An output, from start to finish

Suppose your repo holds a booking tool for boat tours, and one of your agents answers support issues from the docs. It can read files. It can't change them.

1. A customer asks how to get a refund for a cancelled tour. The agent answers from the refund doc and adds: "I've updated the docs to make this clearer." It updated nothing. It can only read.
2. The runner writes a run record, and the code checks pass. The reply is within its length limit, contains no phrase it mustn't, links only to files that exist and holds no credential. It's well-formed, and that's all code can confirm.
3. That week the `weekly-read` issue says runs are waiting. You build the review sheet, find the reply and label it `fail`, with the reason "says it updated the docs; it can only read them".
4. A script can't tell this failure apart, because honest replies use the same words. A check that the reply must not contain "updated the docs" would also fail "I haven't updated the docs", and a check on "update" would fail "I couldn't update the docs". So no case is written. The label stays, with its reason.
5. The same reason turns up in your labels week after week, and the failure earns a judge. Prompt 3 groups your reasons, proposes this one and asks you to confirm it. The judge's question: does this reply say the agent changed a file? For an agent that can only read, any yes is a fail.
6. Before the judge runs at all, it's measured. Your labels are split in two by a hash of each record's id. The judge is written from one half and tested on the other, which it has never seen. You get its catch rate, its pass rate on good work and every record where it disagreed with you. From then on its verdict appears beside yours in the weekly read, once you've given yours.

Now a different failure. The agent tells a customer that refunds take 72 hours, and the refund doc says 48. You label it fail, and this time a script can tell right from wrong. The case saves the customer's question and a check that the reply must not contain "72 hours". `add_case.py` confirms that the check fails the reply you labelled, and writes the case when you pass `--yes`. From then on, every pull request that changes the agent's prompt, model or tools runs it again.

The two failures took different routes for one reason: whether a script could tell the failing reply from a good one.

## Why the prompts are built this way

**Every agent starts through one runner.** The workflow check fails a job that calls the CLI directly, so no workflow can forget the limits, the pinned model or the run record. Left to itself, the CLI sets no turn limit: "No limit by default." [5]

**Each agent names a pinned model, never an alias that moves.** A regression result means little if the model changed underneath it.

**Every run has three limits: turns, dollars and minutes.** The dollar cap is the CLI's own estimate, and its documentation says "Spend can pass the cap". [5] Keep a spend limit on the account as well. The job's timeout runs a few minutes past the agent's, so the runner ends the run first and the record still gets written.

**No agent may change what checks it.** Whatever its entry says, an agent can't touch `agents.json`, `.github/`, `scripts/`, `tests/`, `evals/` or an instruction file, and a change that deletes a test file or removes a test fails. One study gave agents tasks whose tests contradicted the instructions, so any pass was a cheat. Some models passed mostly by "modifying test cases", and "Hiding tests from agents reduces cheating success rate to near zero." [6]

**Labels and judges say pass or fail, never a score.** As one guide to model judges puts it, "People don't know what to do with a 3 or 4." [7] A judge may also answer "unknown". Each label carries a date and a reason, and you may relabel. One study named the effect "criteria drift": "users need criteria to grade outputs, but grading outputs helps users define criteria." [8]

**Cases come only from real failures, and code grades them.** [3] `add_case.py` refuses a check that passes on the very output you failed, and never writes over a case.

**The regression set runs whenever an agent changes**: its prompt, its entry in `agents.json`, its cases, or the runner. After an incident in which three changes, one of them a system prompt change, lowered quality and "neither our internal usage nor evals initially reproduced the issues", Anthropic committed to "run a broad suite of per-model evals for every system prompt change". [9] The job always runs and reports. A job skipped by a condition reports "Success" and can satisfy a required check, and a workflow skipped by a path filter leaves its check pending and blocks the merge. [10] Model outputs vary between runs, so with `--trials K` a case passes only if all K trials pass. [3]

**A judge is measured with two rates.** Its **catch rate** is the share of outputs you labelled fail that it also fails. Its **pass rate on good work** is the share you labelled pass that it also passes. Overall agreement hides a judge that passes everything. In the words of one guide, "Raw agreement can be misleading when classes are imbalanced." [7] One study found that "judges with high percent agreement can still assign vastly different scores". [11] The validator won't write a result from fewer than 20 held-back labels or fewer than 8 fails, unless you pass `--accept-small`, which marks every verdict "small sample".

**A judge runs only with a validation for its exact file and model.** One paper found that "An LLM-as-judge score can move even when the candidate responses stay fixed, simply because the evaluator has changed." [12]

**The judge advises, and no required check depends on it.** One team runs agent evals on every pull request as context rather than as a gate, because its workflows are non-deterministic, and gets "very strong signal when they all fail, and strong signal when they all pass". [13]

**The sources disagree on which model should judge.** A comment in the example code in Anthropic's documentation calls it "Generally best practice to evaluate with a different model from the one used to generate the evaluated output". [1] The evals FAQ says judging with the same model "is usually fine". [2] Prompt 3 has Claude quote the documentation and ask you.

## What to expect when you run it

**Agent pull requests need their own identity.** A pull request opened with the workflow's built-in `GITHUB_TOKEN` starts no workflows, so it gets no checks at all. Use a GitHub App token or a bot account's token. Prompt 1's report covers the setup.

**Prompt 2 won't label for you.** It runs an agent a few times, builds the sheet and stops. A week's read at the cap of 30 records takes roughly 30 to 60 minutes, as an estimate. If you skip a week, nothing is lost: unlabelled records come up again.

**Each regression set starts empty, and that's fine.** It grows from the failures you label.

**Prompt 3 may tell you that you don't need a judge yet, and stop.** That's a good outcome.

**A perfect score on a small set proves little.** A judge that scores 100% on a small or repetitive held-back set hasn't been shown to be perfect, and the validator warns when held-back outputs repeat ones in the writing half. Read the disagreements yourself. In Anthropic's words, "You won't know if your graders are working well unless you read the transcripts and grades from many trials." [3]

## What this chapter doesn't do

- **Code checks can't tell whether an answer is right, invented or off in tone.** The weekly read is where you find those.
- **The regression set says nothing about failures you haven't seen.**
- **The judge reads the output text only.** It can't tell whether the agent really did what it says, or whether the facts are right.
- **It enforces nothing until the default branch requires the check.**
- **It leaves out what has no solid evidence behind it.** Nothing solid says at what agreement a judge is good enough, how often a validated judge needs validating again, or when to give an agent more autonomy or take it away. So there's no autonomy ladder, no dashboard, no 1-to-5 score, no panel of judges, and no merge blocked on a judge's verdict.

## Sources

1. Anthropic, Claude Platform documentation, "Define success criteria and build evaluations". <https://platform.claude.com/docs/en/test-and-evaluate/develop-tests>
2. Hamel Husain and Shreya Shankar, "AI Evals: Everything You Need to Know". <https://hamel.dev/blog/posts/evals-faq/>
3. Anthropic, "Demystifying evals for AI agents", 2026. <https://www.anthropic.com/research/demystifying-evals-for-ai-agents>
4. METR, "Many SWE-bench-Passing PRs Would Not Be Merged into Main", 2026. <https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/>
5. Anthropic, Claude Code documentation, "CLI reference". <https://code.claude.com/docs/en/cli-reference>
6. Zhong, Raghunathan and Carlini, "ImpossibleBench: Measuring LLMs' Propensity of Exploiting Test Cases", 2025. <https://arxiv.org/html/2510.20270>
7. Hamel Husain, "Using LLM-as-a-Judge For Evaluation: A Complete Guide", 2024. <https://hamel.dev/blog/posts/llm-judge/>
8. Shankar et al., "Who Validates the Validators?", 2024. <https://arxiv.org/abs/2404.12272>
9. Anthropic, "An update on recent Claude Code quality reports", 2026. <https://www.anthropic.com/research/april-23-postmortem>
10. GitHub Docs, "Troubleshooting required status checks". <https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks>
11. Thakur et al., "Judging the Judges: Evaluating Alignment and Vulnerabilities in LLMs-as-Judges", 2024. <https://arxiv.org/abs/2406.12624>
12. Yang, Hou and Yang, "When the Judge Changes, So Does the Measurement", 2026. <https://arxiv.org/abs/2607.08535>
13. Will Larson, "Building an internal agent: Evals to validate workflows", 2025. <https://lethain.com/agents-evals/>
