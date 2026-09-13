# Cold-start exercise

A 45-minute exercise for the prospective second owner of this repo, done with the original author silent — they answer nothing during the exercise, only afterward. The goal is not to pass; it's to produce a list of "things I couldn't find." That list becomes the next docs PR.

Do the three tasks in order. Keep notes as you go — anything you had to guess, anything the docs didn't answer, anything that took longer than it should have.

## 1. Trace (15 min)

A lead was upserted to the CRM as `enrolled` yesterday. Name every file that decided that — the workflow that scored it, the workflow that performed the CRM write, the rubric or schema each one checked against, and the exact condition that promotes a lead from scored to upserted.

Write down the files in the order you found them, and how you found each one (grep, a README, a workflow's own comments).

## 2. Run (15 min)

Dispatch the data-validate check against the full data tree (advisory only — never blocks anything):

```bash
gh workflow run data-validate.yml
```

Read the run summary. Write down, in your own words, what it actually checked and why someone would want to know the answer.

## 3. Fix (15 min)

The night before this exercise, the original author plants exactly one bug on a branch, from this list:
- a wrong workflow filename cited in an agent's CLAUDE.md "reads/writes" section
- a `MONITORED` window in `lib/heartbeat.py` changed from its real value to something implausible
- a misspelled secret or repo-variable name in a workflow's `env:` block

Find it and fix it via a PR — branch, commit, PR, following whatever merge convention this instance has settled on. Don't ask what the bug is; find it the way a real drift would surface (something a doc claims that the workflow file doesn't back up).

## Scoring

There is no pass/fail. At the end, write down everything from your notes that you could not find, or could only find by asking, or that took real digging. That list — not a score — is what matters. Hand it to whoever runs docs PRs here; each item becomes one.
