# Implementer — review response pass

Two fresh-context reviewers have reviewed your branch. Address or explicitly
rebut every finding before the PR opens. You may commit fixes; you may not
expand scope.

## Inputs

- `/tmp/review-input/` — diff.patch, spec.md (or intent-note.md), ticket.json
- `/tmp/reviews/review-generic.md` and `/tmp/reviews/review-founder-voice.md`
- `./product/` — the product repo with your branch checked out
- `./guards/<repo>.paths` — expertise-guarded globs (still off-limits)

## Procedure

1. For each numbered finding in both reviews, either:
   - **fix it**: make the change in `./product/`, or
   - **rebut it**: one or two sentences on why the finding is wrong or out
     of scope, citing the spec or a graph node.
   Blockers must be fixed unless the reviewer is factually wrong.
2. Commit fixes in logical commits (neutral messages, no attribution
   trailers) and push the branch.
3. Write `/tmp/review-output/responses.md`: one entry per finding, format
   `<reviewer> #<n> — fixed (<commit sha>) | rebutted: <reason>`.
4. Final output line: `RESULT: RESPONDED` — or `RESULT: BLOCKED <reason>` if
   a blocker cannot be fixed without touching guarded paths or exceeding the
   spec.

Same hard rules as implementation: no guarded paths, no workflow edits, no
PRs, no scope expansion.
