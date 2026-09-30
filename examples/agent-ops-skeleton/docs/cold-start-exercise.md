# Cold-start exercise

A 45-minute exercise for the prospective second owner of this repo, done with the original author silent — the author answers nothing during the exercise, only afterward. The goal is not to pass; it's to produce a list of "things I couldn't find." That list becomes the next docs PR.

Do the three tasks in order. Keep notes as you go — anything you had to guess, anything the docs didn't answer, anything that took longer than it should have.

## 1. Trace (15 min)

A spec PR was converted to draft and labeled `claims:contradicted`. Name every file that decided that — the workflow that ran the check, the script (if any) that did the actual comparison, the schema or fixture it validated against, and the exact condition that flips a PR from open to draft with that label.

Write down the files in the order you found them, and how you found each one (grep, a README, a workflow's own comments).

## 2. Run (15 min)

Dispatch `install-preflight.yml` (no model calls, safe to run):

```bash
gh workflow run install-preflight.yml
```

Read the run summary. Write down, in your own words, what it actually checked and why someone would want to know the answer.

## 3. Fix (15 min)

The night before this exercise, the original author plants exactly one bug on a branch, from this list:
- a wrong workflow filename cited in a node README's "Run it by hand" or "Files this node touches" section
- a `MONITORED` window in the heartbeat changed from its real value to something implausible
- a misspelled secret name in a node README's "Secrets and variables" section

Find it and fix it via a PR — branch, commit, PR, following the repo's own merge convention. Don't ask what the bug is; find it the way a real drift would surface (something a README claims that the workflow file doesn't back up).

## Scoring

There is no pass/fail. At the end, write down everything from your notes that you could not find, or could only find by asking, or that took real digging. That list — not a score — is what matters. Hand it to whoever runs docs PRs here; each item becomes one.
