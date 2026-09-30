# Sync marker

This skeleton is a genericized port of a live agent-ops pipeline. It is
re-synced from the source by hand: diff the source's behavior since the last
sync, translate it into this skeleton's placeholders, and leave out anything
specific to one company's product, people, or history.

| | |
|---|---|
| Last synced | 2026-09-30 |
| Previous sync | 2026-08-25 |

What the last sync covered: the ticket status card and drafter outbox; the
claim state machine (`state/transitions.json`) enforced at write time; the
bounded judge → revise → re-judge loop; plan/implement split and the
`run-claude.sh` / `result-line.sh` wrappers; the claim-verify gate; an
enforcing cost ceiling (`budget-guard.yml`); the GitHub App auth pattern; the
orchestrated spec drain and reapers; the lint floor; Dependabot triage in
observe mode; per-node READMEs and the docs-sync check.

What it deliberately left out: company-specific evals (real golden PR sets,
book-derived failure catalogs beyond one starter pattern), internal
assessments and closing reports, and real repo/people/guard lists.
