---
title: "Permissions and secrets, prompt 2: limit what Claude Code can reach"
description: "A prompt that turns on the Claude Code sandbox with credential folders denied, sets strict flags for unattended runs, and adds a credential scan before each commit."
owner: charlcye
status: draft
last_reviewed: 2026-11-14
---

# Prompt 2: Limit what Claude Code can reach

This prompt limits what Claude Code can touch on your laptop and in unattended runs. It turns on the sandbox, denies your credential folders and token variables to shell commands, and adds checks that fail a workflow job that runs Claude without a strict permission mode, a turn limit and a timeout.

Does this slow Claude down? Inside the repo, very little. The sandbox lets shell commands write to the repo and reach the hosts you list, so editing, running tests and running the checks go on as before. A command that needs a denied credential or an unlisted host, such as a push, fails or stops to ask you. The [chapter overview](README.md) explains why the sandbox does the heavy lifting and the deny rules are a second layer.

## What you'll have

- Sandbox settings in `.claude/settings.json`: on, writes limited to the repo, a short host list, credentials denied.
- Deny rules for Claude's file tools on `.env` files and `secrets` folders.
- Four new rules in the workflow check for jobs that run the Claude Code command line: the strict permission mode, a turn limit, a job timeout, and a checkout that doesn't leave the repository token in a file the agent can read.
- `scripts/check_secrets.py` in CI, and a pre-commit hook you install once.
- A notice in the CI job summary when a pull request touches the files it's checked by.
- `docs/setup-claude-code.md`: what is enforced and by what, and the steps only you can do.

## Before you start

Do [prompt 1](prompt-1-lock-your-workflows.md) first. The prompt tells Claude to test the sandbox with decoy files and to leave your real credential files alone. That's an instruction, so ask Claude which files the test opened.

## The prompt

```text
Limit what Claude Code can reach when it works in this repo, on my laptop and in unattended runs. Work in this repo and fit in with what exists. The repo already has scripts/check_workflows.py with tests and CI, docs/terminus/secrets.md, workflow-policy.json, .claude/settings.json and a root CLAUDE.md. If any of those are missing, stop and tell me. I am the only person working on this repo.

Three rules for the whole build:
- Prefer a boundary the operating system or the command line enforces over a rule Claude is asked to follow. Say plainly, for each thing you add, which kind it is.
- Claude Code changes. Before you write any settings entry or command-line flag, read the current Claude Code documentation for it (permissions, permission modes, sandboxing, settings, hooks, the CLI reference and running headless) and follow it. Don't write these from memory. Tell me which pages you read and quote the sentence each choice rests on.
- Don't edit anything outside this repo, and don't read my real credential files to test anything. Use decoys.

Build these, in this order:

1. The sandbox, in the project's committed settings, merged with what is there:
   - turn it on for shell commands
   - writes limited to this repo
   - network limited to a short list of hosts this repo's commands need; propose the list from the scripts and workflows and ask me to confirm it
   - credentials denied: the usual key folders in my home directory (SSH, cloud provider and GitHub CLI credentials), any .env files, and the environment variables that hold tokens; take the variable names from docs/terminus/secrets.md and add the common ones
   - no falling back to running a command outside the sandbox when it fails inside
   If the documentation says any of these can't be set at project level, put them in a file docs/setup-claude-code.md as a block for me to add to my user settings, and say so.

2. Deny rules for Claude's own file tools, in the same settings: reading .env files and any file under a folder named secrets. Add a comment or a line in docs/setup-claude-code.md saying what these rules do not cover.

3. Unattended runs. Extend scripts/check_workflows.py, with tests, so that every job that runs the Claude Code CLI:
   - passes the permission mode that denies anything not on the allowed list
   - sets a limit on turns
   - has a timeout on the job
   - checks the repo out without leaving the token on disk, unless a later step in the same job needs it and says why in a comment
   Then fix the existing workflows so they pass, without changing what they do.

4. scripts/check_secrets.py, standard library only, with tests: scans the files git tracks, or the staged files with "--staged", for strings that look like credentials: private key blocks and the well-known prefixes of API keys and access tokens for the model provider, GitHub, the major clouds and Slack. It prints "path:line: kind" and never the value, and exits 1 on a hit. A line can be excused with the comment "secret-scan: ignore" for test fixtures. Run it in the existing CI check job. Add scripts/install_hooks.sh, which installs a git pre-commit hook that runs it on staged files, and tell me to run it once.

5. A notice for sensitive changes. In the pull-request CI job, list in the job summary any changed file under .github/, .claude/, scripts/ or tests/, and CLAUDE.md, CODEOWNERS and workflow-policy.json, under the heading "This pull request changes the rules it is checked by". It doesn't fail the job.

6. docs/setup-claude-code.md, with the repo's required fields and status "draft", at most 120 lines: what is enforced and by what (sandbox, flags, GitHub), what is advice, the one-time steps on my laptop, and the things only I can do in a web console: one API key per kind of agent, each with its own spending limit; turn on secret scanning and push protection if my plan includes them. Add these as open questions in docs/terminus/secrets.md where they concern a secret.

7. In CLAUDE.md, within its limit, add one line pointing at docs/setup-claude-code.md.

Finish by running all the tests and all the checks and showing me the outputs. Then prove the sandbox works without touching my real credentials: create a decoy secrets file outside the repo's writable area and a decoy token variable, add both to the denied credentials for the test only, start a Claude Code session in this repo from the command line with a shell allowed, ask it to print the decoy file and the decoy variable and to fetch a host that isn't on the list, and show me that all three were refused. Remove the decoys afterwards. If you can't run that test here, say so and give me the exact commands to run it myself.

Then tell me:
- a table of every protection you added: what it stops, what it does not stop, and whether the operating system, the command line, GitHub or only Claude's cooperation enforces it
- the documentation pages you read, and anything they left unclear
- every question that needs my answer
- anything in this prompt you could not do, or did differently, and why
```

## What you should see

Passing tests and checks, then the sandbox test. Claude asks a session to print a decoy file and a decoy token variable and to call a host that isn't on your list, and shows you each one refused. If it can't run the test, it gives you the commands to run it yourself. Claude's report includes a table of every protection, what it stops, what it doesn't, and what enforces it.

If the documentation says a setting can't be set from inside a repo, Claude puts it in `docs/setup-claude-code.md` as a block for your user settings.

## Check it yourself

1. Start Claude Code in the repo and ask it to run `curl https://example.com`. If Claude asks whether to run the command, allow it. The request should then fail, or Claude Code should ask you about the host `example.com`. It shouldn't just succeed.
2. If Claude wrote a user-settings block, add it first. Then ask Claude to run `touch ~/sandbox-test.txt`. The shell should refuse, and the file shouldn't exist. If Claude offers to retry outside the sandbox, decline.
3. In a new file, write `token = ` and then, inside one pair of quotes, `ghp_` followed directly by 36 letters and digits. Stage the file and run `python3 scripts/check_secrets.py --staged`. It should fail with the file, the line and the kind, and it shouldn't print the value. Unstage the file and delete it.
4. If a workflow runs the Claude Code command line, remove its turn limit and run `python3 scripts/check_workflows.py`. It should fail. Put it back.

If step 2 succeeds, check that the sandbox is on in the settings Claude Code loaded, then tell Claude what happened.

## Then finish the job

- Run `bash scripts/install_hooks.sh` once. The prompt leaves this step to you.
- Add the user-settings block from `docs/setup-claude-code.md`, if Claude wrote one.
- Confirm the host list and keep it short, because a command can send data to any host on it.
- In your model provider's console, create one key per kind of agent, each in a workspace with its own spending limit, and record each key's name, never its value, in `docs/terminus/secrets.md`.

## What this doesn't do

- The sandbox covers shell commands. Claude's file tools, its web tool, hooks and connected servers run outside it.
- A per-user temporary folder stays writable.
- The credential scan knows common key formats. It won't catch a password, and it doesn't search your git history.
- A pre-commit hook can be skipped with `--no-verify`. The scan in CI still runs, but only after the commit is pushed, so revoke any key it finds there.
- The notice about changed rules informs you. It doesn't block the merge.
