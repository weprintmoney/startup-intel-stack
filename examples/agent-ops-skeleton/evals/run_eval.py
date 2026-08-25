#!/usr/bin/env python3
"""Golden-set eval harness for the PR judges (code-judge, founder-voice-pr-reviewer).

Fixtures in evals/pr-cases/<slug>/ are historical PRs with known human
verdicts (see MINING-REPORT.md): diff.patch + context.md + expected.json.
The harness runs the UNMODIFIED production judge prompt against each case
and fails on any verdict flip — a flip means the judge drifted (prompt edit,
rubric edit in internal-docs, or model change).

Per-case flow (driven by the judge-evals workflow):
  run_eval.py cases [--only a,b,c]
  run_eval.py setup   --case SLUG [--rubric PATH]
  <workflow runs: claude -p agents/<judge>/CLAUDE.md ...>
  run_eval.py collect --judge J --case SLUG --results DIR
  run_eval.py compare --judge J --results DIR [--only a,b,c]

setup materializes /tmp/review-input/ exactly as production does (diff,
context, rubric, run-meta) so the production prompts run unmodified.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CASES_DIR = REPO / "evals" / "pr-cases"
REVIEW_INPUT = Path("/tmp/review-input")
REVIEW_OUTPUT = Path("/tmp/review-output")

JUDGES = ("code-judge", "founder-voice-pr-reviewer")


def list_cases(only: str | None) -> list[str]:
    slugs = sorted(d.name for d in CASES_DIR.iterdir() if (d / "expected.json").is_file())
    if only:
        wanted = [s.strip() for s in only.split(",") if s.strip()]
        missing = [w for w in wanted if w not in slugs]
        if missing:
            sys.exit(f"unknown case(s): {', '.join(missing)}")
        slugs = wanted
    return slugs


def setup(case: str, rubric: Path) -> None:
    src = CASES_DIR / case
    if not src.is_dir():
        sys.exit(f"no such case: {case}")
    for d in (REVIEW_INPUT, REVIEW_OUTPUT):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    shutil.copy(src / "diff.patch", REVIEW_INPUT / "diff.patch")
    shutil.copy(src / "context.md", REVIEW_INPUT / "context.md")
    if not rubric.is_file():
        sys.exit(f"rubric not found at {rubric} — the workflow must check out internal-docs first")
    shutil.copy(rubric, REVIEW_INPUT / "rubric.md")
    exp = json.loads((src / "expected.json").read_text())
    (REVIEW_INPUT / "run-meta.json").write_text(json.dumps({
        "repo": exp["repo"],
        "pr": exp["pr"],
        "rubric_version": "eval-golden-set",
        "run_url": f"https://github.com/<YOUR_ORG>/agent-ops/evals/{case}",
    }, indent=2))
    print(f"sandbox ready for {case}: {REVIEW_INPUT}")


def collect(judge: str, case: str, results: Path) -> None:
    dest = results / case
    dest.mkdir(parents=True, exist_ok=True)
    wanted = "verdict.json" if judge == "code-judge" else "review.md"
    src = REVIEW_OUTPUT / wanted
    if src.is_file():
        shutil.copy(src, dest / wanted)
    else:
        print(f"::warning::{judge}/{case}: no {wanted} produced")


def actual_verdict(judge: str, case_dir: Path) -> str:
    if judge == "code-judge":
        f = case_dir / "verdict.json"
        if not f.is_file():
            return "MISSING"
        try:
            v = json.loads(f.read_text())
        except json.JSONDecodeError:
            return "UNPARSEABLE"
        for key in ("judge", "verdict", "score", "threshold", "criteria"):
            if key not in v:
                return f"MALFORMED (no {key})"
        return str(v.get("verdict"))
    f = case_dir / "review.md"
    if not f.is_file():
        return "MISSING"
    text = f.read_text().strip()
    first = text.splitlines()[0] if text else ""
    m = re.match(r"VERDICT:\s*(approve|request-changes)\s*$", first)
    return m.group(1) if m else "NO VERDICT LINE"


def compare(judge: str, results: Path, only: str | None) -> int:
    rows, failures = [], 0
    for case in list_cases(only):
        exp = json.loads((CASES_DIR / case / "expected.json").read_text())
        expected = exp["expected"][judge]
        actual = actual_verdict(judge, results / case)
        ok = actual == expected
        if not ok:
            failures += 1
        score = "-"
        vf = results / case / "verdict.json"
        if judge == "code-judge" and vf.is_file():
            try:
                score = str(json.loads(vf.read_text()).get("score", "-"))
            except json.JSONDecodeError:
                pass
        rows.append((case, expected, actual, score, "ok" if ok else "FLIP"))

    header = f"## {judge} golden-set eval — {'FAIL' if failures else 'PASS'} ({len(rows) - failures}/{len(rows)})"
    table = ["| case | expected | actual | score | status |", "|---|---|---|---|---|"]
    table += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |" for r in rows]
    report = header + "\n\n" + "\n".join(table) + "\n"
    print(report)

    import os
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(report + "\n")

    if failures:
        print(f"{failures} verdict(s) diverged from the golden set. If a fixture is "
              f"legitimately outdated (rubric change), update evals/pr-cases/ in the "
              f"same PR as the rubric/prompt change — with a note on why.")
    return 1 if failures else 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["cases", "setup", "collect", "compare"])
    p.add_argument("--judge", choices=JUDGES)
    p.add_argument("--case")
    p.add_argument("--results", type=Path)
    p.add_argument("--only", help="comma-separated case subset")
    p.add_argument("--rubric", type=Path,
                   default=REPO / "internal-docs/07-engineering-docs/code-judge-rubric.md")
    args = p.parse_args()

    if args.command == "cases":
        print("\n".join(list_cases(args.only)))
        return 0
    if args.command == "setup":
        if not args.case:
            sys.exit("setup requires --case")
        setup(args.case, args.rubric)
        return 0
    if args.command == "collect":
        if not (args.judge and args.case and args.results):
            sys.exit("collect requires --judge --case --results")
        collect(args.judge, args.case, args.results)
        return 0
    if not (args.judge and args.results):
        sys.exit("compare requires --judge --results")
    return compare(args.judge, args.results, args.only)


if __name__ == "__main__":
    sys.exit(main())
