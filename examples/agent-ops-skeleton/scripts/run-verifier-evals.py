#!/usr/bin/env python3
"""Golden-set runner for the miner-verify gate (agents/miner-verifier/).

Fixtures live in evals/miner-verify-cases/<slug>/:
  summary.md, findings.json, expected-verdict.json.

Per-case flow (driven by verifier-evals.yml):
  run-verifier-evals.py cases [--only a,b,c]
  run-verifier-evals.py setup   --case SLUG
  <workflow runs: claude -p agents/miner-verifier/CLAUDE.md ...>
  run-verifier-evals.py collect --case SLUG --results DIR
  run-verifier-evals.py compare --results DIR [--only a,b,c]

The verifier's output lives at /tmp/verify/<miner>.json — we materialize
/tmp/verify/<miner>/ inputs (summary + findings + run-meta), the workflow
runs the production verifier prompt unmodified, and `compare` asserts:

- The verifier's `verdict` matches `expected_verdict`.
- For every `expected_claims` entry with `expected_supported: false`, at
  least one verifier output claim with `supported: false` overlaps on a
  distinctive noun/number from the expected claim (substring match on any
  word ≥5 chars in the expected claim string).

Overlap is intentionally forgiving on wording so the golden set survives
minor verifier-prompt phrasing changes. Correctness comes from the
*verdict* + *which specific mismatch* the verifier caught.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CASES_DIR = REPO / "evals" / "miner-verify-cases"
VERIFY_INPUT_ROOT = Path("/tmp/verify")


def list_cases(only: str | None) -> list[str]:
    slugs = sorted(d.name for d in CASES_DIR.iterdir()
                   if (d / "expected-verdict.json").is_file())
    if only:
        wanted = [s.strip() for s in only.split(",") if s.strip()]
        missing = [w for w in wanted if w not in slugs]
        if missing:
            sys.exit(f"unknown case(s): {', '.join(missing)}")
        slugs = wanted
    return slugs


def setup(case: str) -> None:
    src = CASES_DIR / case
    if not src.is_dir():
        sys.exit(f"no such case: {case}")
    exp = json.loads((src / "expected-verdict.json").read_text())
    miner = exp["miner"]
    sandbox = VERIFY_INPUT_ROOT / miner
    if VERIFY_INPUT_ROOT.exists():
        shutil.rmtree(VERIFY_INPUT_ROOT)
    sandbox.mkdir(parents=True)
    shutil.copy(src / "summary.md", sandbox / "summary.md")
    shutil.copy(src / "findings.json", sandbox / "findings.json")
    (sandbox / "run-meta.json").write_text(json.dumps({
        "miner": miner,
        "run_url": f"https://github.com/example-org/agent-ops/evals/{case}",
        "lookback_days": 9,
    }, indent=2))
    print(f"sandbox ready for {case} ({miner}): {sandbox}")


def collect(case: str, results: Path) -> None:
    dest = results / case
    dest.mkdir(parents=True, exist_ok=True)
    exp = json.loads((CASES_DIR / case / "expected-verdict.json").read_text())
    miner = exp["miner"]
    src = VERIFY_INPUT_ROOT / f"{miner}.json"
    if src.is_file():
        shutil.copy(src, dest / "verdict.json")
    else:
        print(f"::warning::{case}: no verifier output at {src}")


def _tokens(text: str) -> set[str]:
    """Distinctive tokens: alphanumeric runs of length ≥5, plus any number."""
    tokens = set(re.findall(r"[A-Za-z0-9-]{5,}", text.lower()))
    tokens |= set(re.findall(r"\b\d+\b", text))
    return tokens


def _matches(expected_claim: str, actual_claims: list[dict]) -> bool:
    """True iff at least one actual claim shares a distinctive token AND is
    marked `supported: false`. Substring match on any word ≥5 chars or any
    number in the expected claim."""
    wanted = _tokens(expected_claim)
    if not wanted:
        # Nothing distinctive to match on — treat as satisfied by any
        # unsupported claim (soft check).
        return any(c.get("supported") is False for c in actual_claims)
    for c in actual_claims:
        if c.get("supported") is not False:
            continue
        haystack = " ".join([
            str(c.get("claim", "")),
            str(c.get("contradiction", "") or ""),
        ]).lower()
        haystack_tokens = _tokens(haystack)
        if wanted & haystack_tokens:
            return True
    return False


def compare(results: Path, only: str | None) -> int:  # noqa: C901 — pre-existing, not a lint-floor refactor
    rows, failures = [], 0
    for case in list_cases(only):
        exp = json.loads((CASES_DIR / case / "expected-verdict.json").read_text())
        vfile = results / case / "verdict.json"
        if not vfile.is_file():
            rows.append((case, exp["expected_verdict"], "MISSING", "FAIL"))
            failures += 1
            continue
        try:
            actual = json.loads(vfile.read_text())
        except json.JSONDecodeError:
            rows.append((case, exp["expected_verdict"], "UNPARSEABLE", "FAIL"))
            failures += 1
            continue
        actual_verdict = actual.get("verdict", "?")
        actual_claims = actual.get("claims", [])

        problems = []
        if actual_verdict != exp["expected_verdict"]:
            problems.append(f"verdict {actual_verdict} != {exp['expected_verdict']}")
        # Each expected unsupported claim must be caught by the verifier.
        for ec in exp.get("expected_claims", []):
            if ec.get("expected_supported") is False:
                if not _matches(ec["claim"], actual_claims):
                    problems.append(f"missed unsupported: {ec['claim']!r}")
        # False positives: clean cases must have no unsupported claims.
        if exp["expected_verdict"] == "supported":
            fp = [c for c in actual_claims if c.get("supported") is False]
            if fp:
                for c in fp:
                    problems.append(f"false positive: {c.get('claim')!r}")

        status = "ok" if not problems else "FAIL: " + "; ".join(problems)
        if problems:
            failures += 1
        rows.append((case, exp["expected_verdict"], actual_verdict, status))

    header = (
        f"## miner-verifier golden-set eval — {'FAIL' if failures else 'PASS'} "
        f"({len(rows) - failures}/{len(rows)})"
    )
    table = ["| case | expected | actual | status |", "|---|---|---|---|"]
    table += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |" for r in rows]
    report = header + "\n\n" + "\n".join(table) + "\n"
    print(report)

    import os
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(report + "\n")

    if failures:
        print(f"{failures} case(s) failed the golden set. Either the verifier prompt "
              f"drifted or a fixture is out of date — the fix goes in the same PR "
              f"as the prompt change, on a `dream/verifier-*` branch.")
    return 1 if failures else 0


def lint() -> int:
    """Fixture invariants a model never touches (deterministic job).

    All three planted fixtures used to announce themselves in
    line 1 of summary.md — a verifier that grepped for the string scored 5/5.
    Fail if any staged file (anything setup copies) carries such a tell.
    """
    problems = []
    tells = ("planted", "mismatch:", "fake evidence", "wrong count", "wrong entity")
    for slug in list_cases(None):
        d = CASES_DIR / slug
        for name in ("summary.md", "findings.json", "expected-verdict.json"):
            if not (d / name).is_file():
                problems.append(f"{slug}: missing {name}")
        for name in ("summary.md", "findings.json"):
            f = d / name
            if not f.is_file():
                continue
            low = f.read_text().lower()
            for t in tells:
                if t in low:
                    problems.append(f"{slug}/{name}: contains the tell '{t}'")
    if problems:
        print("miner-verify fixture lint FAILED:")
        for x in problems:
            print(f"  - {x}")
        return 1
    print(f"miner-verify fixture lint OK: {len(list_cases(None))} fixtures, no planted tells in staged files")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["cases", "setup", "collect", "compare", "lint"])
    p.add_argument("--case")
    p.add_argument("--results", type=Path)
    p.add_argument("--only", help="comma-separated case subset")
    args = p.parse_args()

    if args.command == "cases":
        print("\n".join(list_cases(args.only)))
        return 0
    if args.command == "lint":
        return lint()
    if args.command == "setup":
        if not args.case:
            sys.exit("setup requires --case")
        setup(args.case)
        return 0
    if args.command == "collect":
        if not (args.case and args.results):
            sys.exit("collect requires --case --results")
        collect(args.case, args.results)
        return 0
    if not args.results:
        sys.exit("compare requires --results")
    return compare(args.results, args.only)


if __name__ == "__main__":
    sys.exit(main())
