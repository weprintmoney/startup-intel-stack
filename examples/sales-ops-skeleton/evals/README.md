# Judge golden-set evals

Regression fixtures for the two LLM judges that gate the pipeline. The production agent prompts (`agents/qualifier-critic/CLAUDE.md`, `agents/copy-evaluator/CLAUDE.md`) run **unmodified** in a sandbox seeded with these fixtures; `run_eval.py compare` fails the build if any verdict flips. The point: a rubric edit in internal-docs, a prompt edit here, or a model-version bump cannot silently change what passes the gates.

Run by [`judge-evals.yml`](../.github/workflows/judge-evals.yml) on PRs touching judge prompts or fixtures, weekly (Mon 6 AM ET, to catch internal-docs rubric edits and model drift), and on dispatch.

## Layout

| Path | Contents |
|---|---|
| `qualifier-critic/golden-leads.json` | Fixture leads in enriched-record shape (this skeleton ships ONE toy PASS fixture; your real build wants 10-20) |
| `qualifier-critic/expected.json` | Expected decision (+ optional criteria codes) per lead |
| `copy-evaluator/golden-leads.json` | Fixture leads backing the drafts (ships ONE toy fixture) |
| `copy-evaluator/golden-drafts/` | Touch-1 drafts in queue-file shape (ships ONE PASS + ONE FAIL toy draft) |
| `copy-evaluator/expected.json` | Expected decision per draft |
| `run_eval.py` | `setup` builds the sandbox; `compare` diffs verdicts vs expected |

## Fixture design rules

- **Clear-cut cases only.** LLM judges have scoring noise; borderline fixtures flake. Every fixture should pass or fail with margin, so a flip means real drift, not variance. Reserve a small number of intentional ESCALATE fixtures if you want to pin a specific edge-case rule.
- **Fictional companies** (`source: "golden-eval-fixture"`, `.example` / `.example.com` domains) so fixtures can never be confused with live pipeline leads.
- **No hardcoded dates.** Use `{{TODAY}}` / `{{DAYS_AGO_N}}`; `run_eval.py setup` materializes them at run time so freshness criteria never rot.
- **Every fixture pins a distinct failure mode** — see the `note` field in each `expected.json` entry.

## Updating fixtures

If a rubric change legitimately flips a fixture (e.g. a threshold moves), update the fixture **in the same PR** as the change that flips it, and say why in the PR. Never delete a fixture to make the build green.

When the monthly feedback loop (`feedback-loop.yml`) reports a recurring real-world failure, add a fixture reproducing it — an incident isn't closed until a regression fixture guards it.

## Running locally

```sh
ln -s ~/<YOUR_ORG>/internal-docs internal-docs   # if not already checked out
python evals/run_eval.py setup --judge qualifier-critic --sandbox /tmp/eval-qc
(cd /tmp/eval-qc && claude -p "$(cat ~/sales-ops/agents/qualifier-critic/CLAUDE.md)" --allowedTools "Bash,Read,Write" --max-turns 40)
python evals/run_eval.py compare --judge qualifier-critic --sandbox /tmp/eval-qc
```
