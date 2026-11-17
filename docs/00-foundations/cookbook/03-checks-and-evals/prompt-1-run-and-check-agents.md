---
title: "Checks and evals, prompt 1: run and check your agents"
description: "A prompt that gives every agent one runner with a pinned model and hard limits, writes a record of every run, and adds code checks on what each agent produces and changes."
owner: charlcye
status: draft
last_reviewed: 2026-11-17
---

# Prompt 1: Run and check your agents

This prompt gives every agent one way to run. Each agent gets an entry in `agents.json` with a pinned model, its tools and its limits, and starts only through `scripts/run_agent.py`, which enforces those limits and writes a run record every time. Code checks then test what each agent produces and which files it changes.

Claude starts by showing you a table of every agent it finds in your workflows. Nothing in this prompt uses a model to check anything: every check is a script that gives the same answer every time. The [chapter overview](README.md#who-decides-whether-an-output-is-good) explains why code comes first.

## What you'll have

- **`agents.json`**, with one entry per agent: owner, purpose, prompt file, pinned model, tools, limits, the environment variables it needs, its output checks and the paths it may change.
- **`agents/<name>/`**, holding each agent's prompt, moved out of its workflow unchanged.
- **`scripts/run_agent.py`**, the only way an agent runs. It writes a run record every time, and exits 0 when the run finished and passed its checks, 1 when a check failed, and 2 when the run hit a limit, timed out or the CLI failed.
- **`scripts/check_agent_output.py`**, the code checks on what an agent produces.
- **`scripts/check_agent_diff.py`**, which fails an agent's change when it touches a path the agent may not change, or removes a test.
- **New rules in `scripts/check_workflows.py`**: every agent runs through the runner, in a job with a timeout and a concurrency group.
- **`docs/agents.md`**, generated from `agents.json`. It's the one page that says what runs here.

## Before you start

Do the earlier chapters first: [single source of truth](../00-single-source-of-truth/README.md), [terminus documents](../01-terminus-documents/README.md) and [permissions and secrets](../02-permissions-and-secrets/README.md). This prompt extends the workflow check from the permissions chapter and assumes GitHub Actions.

Have a model in mind for each agent. Claude asks you for one wherever a workflow doesn't pin one, and it won't accept an alias that moves when a new model ships.

## The prompt

```text
Give every agent in this repo one way to run, hard limits, and code checks on what it produces. Work in this repo and fit in with what exists. The repo already has docs/ with required fields and scripts/check_docs.py, scripts/check_workflows.py with tests and CI, workflow-policy.json, docs/terminus/ and a root CLAUDE.md. If any of those are missing, stop and tell me. I am the only person working on this repo.

Some words, so we mean the same thing:
- An "agent" is a job that runs the Claude Code CLI with a prompt and no person watching.
- A "run record" is one file per run: what the agent was given, what it produced, and what the run cost.
- A "code check" is a test a script can decide. It needs no model and gives the same answer every time.

Three rules for the whole build:
- Anything a script can decide goes in a script. Don't use a model to check anything in this prompt.
- Claude Code changes. Before you write any command-line flag, read the current Claude Code CLI reference and the page on running it headless, and follow them. Don't write flags from memory. Tell me which pages you read and quote the sentence each flag rests on.
- No test may call a model or the network. Tests replace the CLI with a fake command.

First read every workflow and tell me, in one table, each agent you find: which workflow and job runs it, where its prompt lives, what it reads, what it produces and where that goes, which tools it has, and what limits it has today. Then build these, in this order:

1. agents.json at the repo root: one entry per agent with
   - "name", "owner", and "purpose" in one sentence
   - "prompt": the path of a file under agents/<name>/ that holds the prompt. Move each prompt out of its workflow into that file, unchanged.
   - "model": a full model name that the model documentation says maps to one fixed version, never an alias that can move. Check the documentation for what counts. If a workflow doesn't pin one, ask me which to use.
   - "tools": the allowed tools, as the workflow has them today
   - "limits": most turns, most dollars per run, and most minutes
   - "env": the names of the environment variables the agent needs, and no others
   - "output": what kind of thing it produces ("json", "markdown" or "diff") and the checks on it (step 3)
   - "may_change": for an agent that edits files, the path patterns it may touch
   Propose the limits and the checks from what each agent does and ask me to confirm them.

2. scripts/run_agent.py, standard library only. "run_agent.py NAME" runs that agent through the Claude Code CLI with the model, tools and limits from agents.json, in the permission mode that denies anything not allowed. It takes the agent's input from a file with "--input PATH" or from standard input. If a prompt has a placeholder where the input goes, keep it and say in agents.json how the runner fills it.
   - It starts the CLI with only the variables listed in the agent's "env", the model key, and the few the CLI itself needs to run. A token that sits in the job's environment and isn't listed never reaches the agent.
   - It writes a run record as JSON into the folder named by "--records DIR" (default runs/, which git ignores): agent name, start time, the model, a hash of the prompt file, the input, the output, turns used, cost and duration as the CLI reports them, and how the run ended.
   - It exits 0 when the run finished and its output passed the checks in step 3, 1 when a check failed, and 2 when the run hit a limit, timed out or the CLI failed. It writes the record in all three cases.
   - "--cli PATH" names the command to run in place of the real CLI, for tests and for step 6.

3. scripts/check_agent_output.py, standard library only. It checks one run record, or every record in a folder, against that agent's "output" entry:
   - for "json": it parses, has the required fields, and each field named in "allowed" holds one of the listed values
   - for "markdown": a length limit, phrases that must appear, phrases that must not, and every relative link points at a file that exists
   - for every kind: no string that scripts/check_secrets.py would flag, if that script exists
   It prints "record: reason" for each failure and exits 1 on any.

4. scripts/check_agent_diff.py, standard library only, for agents whose work lands as a change to the repo. Given an agent name and a base commit, it fails when the change touches a path outside that agent's "may_change"; when it touches agents.json, anything under .github/, scripts/, tests/ or evals/, or an instruction file; or when it deletes a test file or removes a test from one. It prints "path: reason". An agent never gets these paths, whatever "may_change" says.

5. Extend scripts/check_workflows.py, with tests, so that a job that runs an agent fails the check unless it runs it through scripts/run_agent.py, the agent is in agents.json, the job has a timeout that is longer than the agent's minutes by no more than five, so the runner's own timer ends the run first and the record still gets written, and the workflow has a concurrency group so two runs of one agent don't overlap. A job that calls the Claude Code CLI directly fails. Then change the existing workflows to pass, without changing what the agents are asked to do. Leave a disabled workflow disabled. Each agent job uploads its run records as a build artifact.

6. Tests that need no network or model: a passing run; a run that fails each kind of output check; a run that hits each limit; a record is written every time; each rule in steps 4 and 5 with one failing fixture; agents.json entries that are missing a field, name a prompt file that doesn't exist, or use a model alias. Build fixtures in temporary folders, with a small fake CLI script.

7. docs/agents.md, generated from agents.json by "run_agent.py --list-doc": one row per agent with its owner, purpose, model, tools, limits, checks and what it may change. Give it the repo's required fields with status "draft". The CI check fails when it is out of date. This is the one page that says what runs here.

8. CI: run the new tests, check_agent_output.py on any records in the repo's fixtures, and the agents.md freshness check in the existing check job, on every pull request and every push to the default branch. On pull requests opened by an agent, also run check_agent_diff.py against the base branch; tell me how the job knows which agent opened the pull request and what I must set up for that to be reliable.

9. In CLAUDE.md, within its limit, add one line: agents run through scripts/run_agent.py and are listed in docs/agents.md.

Finish by running all the tests and all the checks and showing me the outputs. Then run one agent for real through run_agent.py on a small input I would recognise, show me the run record, and show check_agent_output.py passing on it. If you can't run it here, say so and give me the exact command.

Then tell me:
- the table of agents again, showing what changed for each
- every limit and check you proposed, and the ones that need my answer
- what these checks cannot catch
- the documentation pages you read, and anything they left unclear
- anything in this prompt you could not do, or did differently, and why
```

## What you should see

Before it builds anything, Claude shows you a table of every agent: the workflow and job that runs it, where its prompt lives, what it reads and produces, its tools and its limits today. It then proposes limits and checks for each agent and asks you to confirm them.

After the build you get passing tests and checks, and one real run: a record from one agent on a small input you'd recognise, with `check_agent_output.py` passing on it. The report shows the agent table again with what changed, the documentation pages Claude read, what the checks can't catch, and how CI knows which agent opened a pull request.

## Check it yourself

Script names and flags below are whatever Claude built. If a command differs, ask Claude for the equivalent. Undo each step before you start the next, unless it says to keep the result.

1. In `agents.json`, change one agent's model to `sonnet`. Run `python3 scripts/run_agent.py --list-doc --check`. It should fail and say an alias moves when a new model ships.
2. Add a step to any workflow that runs `claude -p "hi"`. Run `python3 scripts/check_workflows.py`. It should fail and tell you to run the agent through `scripts/run_agent.py`.
3. On a branch named `agent/<an agent's name>/test`, change a file under `tests/` and commit. Run `HEAD_REF=agent/<name>/test PR_AUTHOR='github-actions[bot]' python3 scripts/check_agent_diff.py --pull-request main`. It should fail and say no agent may change anything under `tests/`. Delete the branch.
4. Keep this one. Run one agent on a small input with `python3 scripts/run_agent.py <name> --input <file>`, open the record it wrote under `runs/`, and run `python3 scripts/check_agent_output.py runs`.

If any step passes when it should fail, tell Claude what you did and ask it to fix the check and add a test.

## Then finish the job

- **Answer Claude's questions.** Confirm each agent's model, limits, checks and owner.
- **Set up the identity agent pull requests are opened with.** A pull request opened with the workflow's built-in `GITHUB_TOKEN` doesn't get its checks run automatically. GitHub's documentation says its workflow runs wait in an approval-required state until a person approves them, and a push made with that token outside a pull request starts no workflows. To have checks run without that step, use a GitHub App token or a bot account's token, as the report describes.
- **Require the check on the default branch.**
- **Set a spend limit on the account.** The dollar limit on each run is the CLI's estimate, and spend can pass it.

## What this doesn't do

- **Code checks can't tell whether an answer is right, invented or off in tone.** [Prompt 2](prompt-2-weekly-read-and-regression-set.md) puts those in front of you.
- **The credential check knows well-known prefixes.** It doesn't catch a password with no pattern.
- **The path check sees which files changed.** It can't tell whether the content inside an allowed path is good.
- **A test gutted to always pass, or marked skip, isn't detected.** Only a removed test or a deleted test file is.
- **The workflow check sees a literal call to the CLI.** A wrapper script or a reusable workflow that calls it is invisible to the check.
- **The run record holds the input, the output and the cost.** It doesn't say which pages the agent fetched or which files it read.
- **None of it enforces anything until the default branch requires the check.**
