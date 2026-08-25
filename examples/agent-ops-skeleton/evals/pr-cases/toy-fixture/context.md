# toy-fixture — context

A small, boring change. It exists only so `evals/run_eval.py` can execute
end-to-end when someone clones this template.

## What this change touches

- `src/api/public/workspaces.py` — the `resolve_workspace_slug` helper. One
  guard clause added, docstring updated to describe the new return case.
- `tests/api/public/test_workspaces.py` — one new test covering the
  unauthenticated path.

## Why it's a good fixture

- Small — a reviewer can hold the whole diff in their head.
- Boring — no interesting design tradeoff, so the "correct" verdict is
  unambiguous.
- Touches only a public-API surface path (`src/api/public/**`), which is
  listed in `guards/example-app-service.paths` — so the fixture also
  exercises the `expertise-path-guard` code path.

## Expected human verdict

Approved. Two small nits a real senior reviewer might leave (docstring
could be tighter, `getattr` fallback could be an explicit `hasattr` check)
but nothing merge-blocking.

## Notes for the eval harness

The `expected.json` alongside encodes the pass verdict for both judges
(`code-judge` and `founder-voice-pr-reviewer`). A verdict flip on either
judge should fail `judge-evals.yml` and freeze auto-merge.
