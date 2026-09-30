# miner-verify-cases — golden fixtures for the miner-verify gate

Hand-curated cases that exercise the `agents/miner-verifier/CLAUDE.md`
prompt end-to-end. `.github/workflows/verifier-evals.yml` runs all cases on
a weekly cron (Mon 7 AM ET) and on dispatch. **The verifier must catch all
3 planted mismatches and produce zero false positives on the 2 clean
cases** — that's the golden-set contract.

## Case format

Each case is a subdirectory with three files:

```
<case-slug>/
  summary.md          # the miner's prose summary (input)
  findings.json       # the miner's schema-valid findings (input)
  expected-verdict.json  # what the verifier should conclude (oracle)
```

`expected-verdict.json` shape:

```json
{
  "case": "<slug>",
  "miner": "transcript-failure-miner|review-delta-miner|doc-drift-miner",
  "expected_verdict": "supported|unsupported",
  "expected_claims": [
    { "claim": "<one-line quote or paraphrase>", "expected_supported": true },
    { "claim": "<the planted mismatch, or a specific supported claim>", "expected_supported": false }
  ]
}
```

The runner (`scripts/run-verifier-evals.py`) enforces:

- `verifier_output.verdict == expected_verdict` for every case.
- Each entry in `expected_claims` with `expected_supported: false` must
  correspond to at least one claim in the verifier output with
  `supported: false` whose `claim` text overlaps meaningfully (substring
  match on a distinctive noun/number from the expected claim).

Overlap is intentionally forgiving on wording so the golden set survives
minor verifier-prompt phrasing changes. The pass/fail signal comes from
the *verdict* and from *which specific mismatch* the verifier caught — not
from claim-string equality.

## Cases

| Slug | Miner | Verdict | Point of the case |
|---|---|---|---|
| `clean-01-transcript` | transcript-failure-miner | supported | Summary counts match findings exactly; every citation resolves; no false alarms. |
| `clean-02-doc-drift` | doc-drift-miner | supported | Two contradicted graph nodes; summary counts + node ids all match; no false alarms. |
| `mismatch-01-wrong-count` | doc-drift-miner | unsupported | Summary claims "4 stale ADRs" but findings has 3. Verifier must flag the numeric mismatch. |
| `mismatch-02-fake-evidence` | review-delta-miner | unsupported | Summary asserts a PR reviewer "requested changes" but the cited PR shows an approve review. Verifier must fetch the link and catch the artifact mismatch. |
| `mismatch-03-wrong-entity` | transcript-failure-miner | unsupported | Summary cites session `2026-W34/implement-repo-A.stream.jsonl` but findings' evidence points at `2026-W34/implement-repo-B.stream.jsonl`. Verifier must catch the entity swap. |

## Adding a case

1. Pick the miner it exercises; use the schema at
   `schemas/miner-findings.schema.json` as the source of truth for
   `findings.json`.
2. Write `summary.md` in the voice the corresponding miner writes it —
   short paragraph plus per-finding bullets, per the miner prompt in
   `agents/dream-orchestrator/miners/<miner>.md`.
3. Record the oracle in `expected-verdict.json`. For mismatch cases,
   include enough `expected_claims` entries that the runner can prove the
   verifier caught the *specific* mismatch, not just tripped on something
   else.
4. Do NOT reference real prospect names, secrets, or private customer
   details. All URLs must be to public repos or synthetic placeholders.
