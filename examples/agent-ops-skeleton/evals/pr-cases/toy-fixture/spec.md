# toy-fixture — null-check `resolve_workspace_slug`

**Repo:** `<YOUR_ORG>/example-app-service`
**PR:** #1 (fabricated)

> Toy fixture used by `evals/run_eval.py` to prove the harness runs. This is
> not a real PR. Replace this directory with 20–30 hand-labeled fixtures
> from your own product-repo history before wiring `judge-evals.yml` into
> anything gated.

## Problem

`resolve_workspace_slug` in `src/api/public/workspaces.py` currently assumes
its `request` argument always carries a populated `user` attribute. On
unauthenticated requests to the public endpoint, the attribute is `None`,
and the helper raises `AttributeError` before the framework's 401 handler
runs. The stack trace ends up in the error log as an INTERNAL rather than a
clean 401.

## Constraints

- Public-API surface behavior does not change for authenticated requests.
- The 401 response body and status code stay identical to the framework
  default — no bespoke error format.
- The helper stays synchronous; no new IO.

## Relevant decisions

- ADR-014 "Public API error taxonomy": internal errors are reserved for
  unrecoverable server-side failures. Auth failures are 401, not 500.
- `internal-docs/07-engineering-docs/invariants.md` §3.2: public endpoints
  never emit an `AttributeError` upstream of the framework's error handler.

## Success criteria

- Calling `resolve_workspace_slug(request)` on a request with `user=None`
  returns `None` instead of raising.
- Existing authenticated-path tests still pass without modification.
- A new test covers the unauthenticated path and asserts the returned
  value is `None`.

## Out of scope

- Rewriting the auth middleware.
- Refactoring the wider `workspaces.py` module.
- Any change to the 401 response body.

## Implementation notes

- Add an early `if getattr(request, "user", None) is None: return None`.
- Do not use a bare `try/except AttributeError` — silent swallow of
  attribute errors elsewhere in the helper is not desired.
- Update the docstring to name the `None` return case explicitly.

## Verification plan

- `pytest tests/api/public/test_workspaces.py -k resolve_workspace_slug`
  passes locally and in CI.
- A new test `test_resolve_workspace_slug_unauthenticated` asserts the
  `None` return.
- Log inspection on a manual unauthenticated request no longer shows an
  `AttributeError` stack trace before the 401.
