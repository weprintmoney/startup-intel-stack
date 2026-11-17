---
title: "Permissions and secrets, prompt 1: lock your workflows"
description: "A prompt that adds a check on every GitHub Actions workflow, a names-only list of secrets, and a pause switch that stops the job when it can't be read."
owner: charlcye
status: draft
last_reviewed: 2026-11-14
---

# Prompt 1: Lock your workflows

This prompt reads every workflow in your repo, tells you what each job can reach, and adds a check that fails when a job can reach too much. It also lists your secrets by name and adds a pause switch, a repository variable that stops a job unless it reads exactly `false`.

Claude starts by showing you a table of what exists. A workflow is usually written to get a job done, and what it can reach is easy to leave unexamined. The check sorts jobs by whether they read outsider text and whether they hold power; the [chapter overview](README.md#outsider-text-and-power) explains both terms.

## What you'll have

- **`scripts/check_workflows.py`**, the workflow check, run in CI on every change.
- **`docs/terminus/secrets.md`**, listing every secret your workflows name, with questions for you about its kind, reach and rotation date.
- **`workflow-policy.json`**, naming the jobs that send or post outside the repo, the jobs that read outsider text in ways the check can't see, and any exceptions you accept.
- **`scripts/require_not_paused.sh`**, a pause check that stops the job unless the switch reads exactly `false`.
- **Your existing workflows**, changed so the check passes, or switched to manual start where they can't pass.

## Before you start

Do the [single source of truth](../00-single-source-of-truth/README.md) and [terminus documents](../01-terminus-documents/README.md) chapters first. This prompt assumes GitHub Actions.

If a scheduled job sends email or posts anywhere, read [Then finish the job](#then-finish-the-job) before you run the prompt. Once the prompt adds or replaces that job's pause check, the job stops until you create its switch.

## The prompt

```text
Lock down this repo's automation. Work in this repo and fit in with what exists. The repo already has scripts/check_docs.py with tests and a CI job, docs/terminus/, a CODEOWNERS file and a root CLAUDE.md. If any of those are missing, stop and tell me. I am the only person working on this repo.

The idea for the whole build: what stops an agent from doing damage is what it can reach, not what it was told. So the rules below are about tokens, permissions and which jobs get which secrets, and each one is a check that fails. Two terms:
- A job "reads outsider text" when a stranger can write something it reads. That is the case when its workflow is triggered by an issue, an issue comment, a pull request, a pull request review or review comment, or a discussion; when its agent is allowed a tool that fetches from the web; when its commands read issues, comments or pull requests; or when I have listed it under "reads_outsider" in the policy file (step 3).
- A job "holds power" when it has any write permission or is given any secret other than the model API key. The built-in GITHUB_TOKEN counts through the job's permissions, not as a secret.
A job that runs an agent with a shell must never do both.

First read every file under .github/workflows/ and tell me, in one table, for each job: what triggers it, what permissions it has, which secrets it gets, whether it runs an agent and with which tools, and whether it reads outsider text, holds power, or both. Then build these, in this order:

1. scripts/check_workflows.py. You may use PyYAML for this script only; pin it in a requirements file and install it in CI. With no arguments it checks every workflow, prints "file: job: reason" for each problem and exits 1 if there are any:
   - a workflow with no top-level permissions block, or one whose top-level block grants any write. Write permissions go on the job that needs them, each with a comment saying why.
   - the pull_request_target trigger
   - an agent run (any command that starts the Claude Code CLI, or the Claude Code action) with no explicit list of allowed tools, or with a flag that skips permission checks
   - a job that reads outsider text, holds power, and runs an agent that has a shell
   - a secret named in a workflow that is not in the secrets list (step 2), and, as a warning only, a secret in the list that no workflow names
   - a job listed under "acts_outside" in the policy file (step 3) that does not run the pause check before it acts
   "--root PATH" points at another tree, for tests. Exit 2 with a clear message if there are no workflows.

2. docs/terminus/secrets.md, with the repo's required fields and status "draft": one table with the columns Name | Used by | Kind | What it can do | Where it is set | Created | Rotate by. Fill Name and Used by from the workflows. Leave the others as questions for me under "Open questions"; don't guess. It holds names only. Add a check to scripts/check_workflows.py that fails if this file contains anything that looks like a secret value, and warns when a "Rotate by" date has passed. If a SECRETS.md or similar already exists, move what it says into this file and replace it with a pointer.

3. workflow-policy.json at the repo root: "acts_outside", a list of workflow jobs that send messages or post to other services; "reads_outsider", a list of jobs that read text a stranger can write in a way the check cannot see, such as an inbox or a feed; and "exceptions", a list of {workflow, job, rule, reason} entries for cases I have accepted. Propose the first two lists from what you read and ask me to confirm them. Leave exceptions empty.

4. scripts/require_not_paused.sh NAME: reads the environment variable NAME and exits 0 only when its value is exactly "false". An unset or empty variable, or any other value, exits 1 with a message that says how to create the repository variable. The switch fails closed. A workflow passes the value in from the "vars" context, for example NAME: ${{ vars.NAME }}, so no token and no API call are involved. Give it tests.

5. Tests for scripts/check_workflows.py that need no network: one passing set of workflows, and one failing fixture for each rule in step 1 and step 2. Build fixtures in temporary folders.

6. CI: run these tests and scripts/check_workflows.py in the existing check job, on every pull request and every push to the default branch, not limited to certain paths.

7. Fix the existing workflows so the check passes, without changing what they do: add or narrow permissions blocks, move write permissions to the job, add the allowed-tools list an agent run is missing, replace a pause check that can fail open with the script from step 4. Where a workflow cannot pass without changing what it does (for example a job that reads outsider text and holds power), don't rewrite it and don't add an exception. Disable it: make workflow_dispatch its only trigger, give it a read-only top-level permissions block, give its agent an explicit tool list with no shell, and say in a comment at the top that it is disabled and why. Then tell me what a safe version would look like, with the reading and the acting in separate jobs, and offer to build it.

8. In CLAUDE.md, within its limit, add one line: never add a workflow, a secret or a permission without running scripts/check_workflows.py.

Finish by running all the tests, the docs check and the workflow check, and show me the outputs. Then tell me:
- the table from the start, updated to show what changed
- the repository settings I should turn on, as a list I can follow: the default permission for the workflow token, whether Actions may create and approve pull requests, protection for the default branch, secret scanning and push protection, and anything my plan may not include. Tell me; don't change repository settings yourself.
- every question in docs/terminus/secrets.md and workflow-policy.json that needs my answer
- anything in this prompt you could not do, or did differently, and why
```

## What you should see

Before it builds anything, Claude shows you a table of every job: its triggers, permissions, secrets and agent tools, and whether it reads outsider text, holds power or both. After the build you get passing tests, a passing workflow check and the same table, updated to show what changed.

The report also names any workflow Claude disabled and describes a safe version of each, with the reading and the acting in separate jobs. It ends with the repository settings to turn on and every question you need to answer.

## Check it yourself

If Claude created a requirements file for the check, install it first with `python3 -m pip install -r` followed by the file's name. Then try each step below, and undo each edit before you start the next.

1. Add `issues: write` under the top-level `permissions:` of any workflow. Run `python3 scripts/check_workflows.py`. It should fail and name the top-level write.
2. Add a line to any step's `env:` that names a secret you don't have, such as `NEW_KEY: ${{ secrets.NEW_KEY }}`. The check should fail and say the secret isn't in `docs/terminus/secrets.md`.
3. Run `SENDING_PAUSED= bash scripts/require_not_paused.sh SENDING_PAUSED`. It should exit with an error and tell you how to create the variable. Run it again with `SENDING_PAUSED=false` in front, and it should pass.
4. If a workflow was disabled, look at the commit that disabled it with `git show`, and put back its trigger, permissions and tool list by hand. The check should fail and name the job as reading outsider text, holding power and running an agent with a shell.

If any step passes when it should fail, tell Claude what you did and ask it to fix the check and add a test.

## Then finish the job

The prompt leaves these steps to you.

- **Create the pause switches.** For each job that sends or posts, create its pause variable with the value `false` when you're ready for it to run. Set it to `true` to pause.
- **Answer the questions in `docs/terminus/secrets.md`.** Compare the list with the secrets in your repository settings, and delete any that nothing uses.
- **Confirm the two lists in `workflow-policy.json`.**
- **Turn on the repository settings Claude listed.** Check each one against GitHub's documentation first.
- **Decide on each disabled workflow.** Ask Claude to build the safe version, or leave it off.

## What this doesn't do

- **It reads workflow files.** It can't see an agent that a script starts, or a secret that sits in your settings and that no workflow names.
- **It can't tell that a shell command fetches a web page, a feed or an inbox.** A job like that counts as reading outsider text only once you list it under `reads_outsider` in `workflow-policy.json`.
- **It doesn't change repository settings.** Until the default branch requires the check, a failing change can still merge.
- **A two-job split limits what a stranger's text can reach.** The agent in the first job can still be talked into a wrong answer.
