# claim-verify-cases — golden fixtures for the claim-verify gate

Hand-curated cases that exercise `scripts/verify-claims.py` and the
`agents/claim-verifier/CLAUDE.md` prompt end-to-end.
`.github/workflows/claim-verify-evals.yml` runs them on PRs touching the
gate, on a weekly cron (Mon 7 AM ET) and on dispatch. **The gate must
produce the expected verdict on all 7 cases, catch every planted claim, and
produce zero false positives on the 5 clean cases** — that's the contract.

A third, narrower check rides alongside the deterministic layer:
**`scripts/check-citation-root-coverage.py`** asserts that
every citation root `scan_path_citations` knows about
(`verify-claims.py`'s `CITATION_ROOTS`) has at least one clean case here
that resolves a real `path:line` against it. It fails CI the moment a new
root is added to `CITATION_ROOTS` without a matching case — the gap that
let the `agent-ops` root ship with nothing exercising it end to
end, burning three spec-draft attempts before the live miss was
caught.

Two layers, two checks:

- **Deterministic** (`run-claim-verify-evals.py deterministic`, no API key):
  every `expected_deterministic` claim is caught by the pre-pass with the
  right verdict, and clean cases produce no deterministic
  contradicted/unverified claims. Runs on every PR as a plain unit-style
  check.
- **Model** (`setup` → `claude -p` → `collect` → `compare`, needs the key):
  the aggregated verdict matches `expected_verdict`; each
  `expected_claims` entry with a non-verified verdict is matched by a
  final claim with that verdict and a shared distinctive token; clean cases
  have no contradicted/unverified claims at all.

Token overlap is intentionally forgiving on wording (same rule as
`miner-verify-cases`) so the set survives prompt rephrasing — correctness
comes from the verdict and from *which* claim was caught.

## Layout

```
_fixtures/                # shared synthetic internal-docs / docs-public / product trees
<case-slug>/
  case.json               # kind, artifact, expected_verdict, expected_claims, expected_deterministic
  artifact.md | .json     # the spec (markdown) or release-findings (JSON) under test
```

`case.json`:

```json
{
  "case": "<slug>",
  "kind": "spec | release-findings",
  "artifact": "artifact.md",
  "artifact_ref": "<spec path or release tag>",
  "expected_verdict": "verified | unverified | contradicted",
  "expected_claims": [ { "claim": "<paraphrase>", "expected_verdict": "..." } ],
  "expected_deterministic": [ { "claim": "<paraphrase>", "verdict": "..." } ],
  "point": "<one sentence on what the case proves>"
}
```

## Cases

| Slug | Kind | Verdict | Point of the case |
|---|---|---|---|
| `clean-01-spec-cited` | spec | verified | Every `path:line` resolves and supports its sentence; graph ids exist; `v0.17.0` in changelog. No false alarms. |
| `clean-02-findings` | release-findings | verified | Two market-worthy findings match the changelog; evidence paths exist and support the scored dimension. Not-market-worthy findings are out of scope. |
| `clean-03-spec-historical` | spec | verified | **Calibration.** Retired phrases quoted historically ("used to point it at Postgres", "MySQL was never supported"). Pre-pass hands them to the model as `pending`; the model must not flag them. |
| `clean-04-spec-internal-docs-cited` | spec | verified | **Citation-root coverage.** Cites `07-engineering-docs/terminus/invariants.md:17` (INV-01) — the first case to resolve a path-citation against the `internal-docs` root rather than `product`. |
| `clean-05-spec-agent-ops-cited` | spec | verified | **Citation-root coverage.** Cites `guards/example-app-sdk-js.paths:2` — the `agent-ops`-root citation shape that PR #81 fixed after it shipped with zero golden-set coverage. |
| `planted-01-spec-postgres` | spec | contradicted | Ticket #18 AC: "example-app supports Postgres storage" is contradicted by changelog / behavior matrix / VA-01, and `config.py:7` does not say what the spec claims. Deterministic layer catches the invented `postgres_pool.py` and unknown `adr-0041`. |
| `planted-02-findings-retired-phrase` | release-findings | contradicted | Ticket #18 AC: a finding summary using "sits in front of" / "separates compute from storage" is contradicted **deterministically** — findings become prospect-facing tickets. Second finding is clean. |

## Adding a case

1. Decide which layer should catch it. If a grep can decide it, it belongs
   in `verify-claims.py` + `expected_deterministic`, not in the prompt.
2. Write the artifact in the producing agent's voice (spec-drafter's
   7-section template; miner's `release-findings.schema.json`). Cite only
   paths that exist under `_fixtures/product/`, `_fixtures/internal-docs/`
   or `_fixtures/agent-ops/` and check the line numbers — a `spec` case can
   cite any of the three (`--product` / `--internal-docs` / `--agent-ops`
   are all passed for `kind: spec` in `materialize()`); a `release-findings`
   case only gets `--internal-docs`.
3. Record the oracle in `case.json`. For planted cases, include enough
   `expected_claims` that the runner proves the gate caught the *specific*
   planted claim, not just tripped on something else.
4. Run `python3 scripts/run-claim-verify-evals.py deterministic --only <slug>`
   locally — it needs no API key.
5. If `verify-claims.py` ever grows a new citation root, add a clean case
   here that resolves a path against it — `check-citation-root-coverage.py`
   fails CI otherwise (run it locally: `python3
   scripts/check-citation-root-coverage.py`, also no API key).
6. No real prospect names, secrets, or private customer details. URLs point
   at `example-org/*` or are synthetic.
