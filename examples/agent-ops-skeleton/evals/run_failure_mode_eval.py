#!/usr/bin/env python3
"""Eval harness for the failure-mode fixtures (evals/failure-mode-cases/).

Honest evals: an earlier harness handed the reviewer the answer
four ways and graded a single verdict bit. Now:

  * the sandbox gets diff.patch + context.md only — never notes.md (the
    reviewer note and pattern line), never pattern_id/book_ref in run-meta,
    and a run_url that does not spell the slug;
  * the rubric is staged for code-judge only (production founder-voice-pr-reviewer
    never sees one);
  * the judge runs with cwd = a sandbox dir holding a sanitized
    failure-mode catalog and the verdict schema, so it cannot grep
    expected.json or the fixture tree (--sandbox);
  * grading is on should_flag via flag_terms, control fixtures must pass,
    and MISSING/MALFORMED are reported apart from FLIP (eval_lib.grade).

Per-case flow (driven by .github/workflows/failure-mode-evals.yml):
  run_failure_mode_eval.py cases [--only a,b] [--kind buggy|control]
  run_failure_mode_eval.py setup   --case SLUG --judge J [--rubric PATH] [--sandbox DIR]
  <workflow runs: (cd SANDBOX && claude -p agents/<judge>/CLAUDE.md ...)>
  run_failure_mode_eval.py collect --judge J --case SLUG --results DIR
  run_failure_mode_eval.py compare --judge J --results DIR [--only a,b] [--summary PATH]
  run_failure_mode_eval.py lint    # fixture invariants, no model (deterministic job)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_lib as L  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SUITE = "failure-mode-cases"
CASES_DIR = REPO / "evals" / SUITE
REVIEW_INPUT = Path("/tmp/review-input")
REVIEW_OUTPUT = Path("/tmp/review-output")
JUDGES = ("code-judge", "founder-voice-pr-reviewer")
SANDBOX_ONLY = ("diff.patch", "context.md")     # notes.md never crosses


def load_expected(case: str) -> dict:
    return json.loads((CASES_DIR / case / "expected.json").read_text())


def list_cases(only: str | None, kind: str | None = None) -> list[str]:
    slugs = sorted(d.name for d in CASES_DIR.iterdir() if (d / "expected.json").is_file())
    if kind:
        slugs = [s for s in slugs if load_expected(s).get("kind", "buggy") == kind]
    if only:
        wanted = [s.strip() for s in only.split(",") if s.strip()]
        missing = [w for w in wanted if w not in slugs]
        if missing:
            sys.exit(f"unknown case(s): {', '.join(missing)}")
        slugs = wanted
    return slugs


def setup(case: str, judge: str, rubric: Path, sandbox: Path | None) -> None:
    src = CASES_DIR / case
    if not src.is_dir():
        sys.exit(f"no such case: {case}")
    for d in (REVIEW_INPUT, REVIEW_OUTPUT):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    for name in SANDBOX_ONLY:
        shutil.copy(src / name, REVIEW_INPUT / name)
    if judge == "code-judge":
        if not rubric.is_file():
            sys.exit(f"rubric not found at {rubric} — the workflow must check out internal-docs first")
        shutil.copy(rubric, REVIEW_INPUT / "rubric.md")
    (REVIEW_INPUT / "run-meta.json").write_text(json.dumps({
        "repo": "example-org/example-app-core",
        "pr": 0,
        "rubric_version": "failure-mode-eval",
        "run_url": L.neutral_run_url(SUITE, case),
    }, indent=2))
    if sandbox is not None:
        L.make_sandbox(sandbox, REPO)
    print(f"sandbox ready for {case} ({judge}): {REVIEW_INPUT}" + (f", cwd {sandbox}" if sandbox else ""))


def collect(judge: str, case: str, results: Path) -> None:
    dest = results / case
    dest.mkdir(parents=True, exist_ok=True)
    wanted = ("verdict.json", "findings.md") if judge == "code-judge" else ("review.md",)
    got = 0
    for name in wanted:
        src = REVIEW_OUTPUT / name
        if src.is_file():
            shutil.copy(src, dest / name)
            got += 1
    if got == 0:
        print(f"::warning::{judge}/{case}: no {wanted[0]} produced (MISSING)")


def compare(judge: str, results: Path, only: str | None, summary: Path | None) -> int:
    rows = []
    for case in list_cases(only):
        exp = load_expected(case)
        expected = exp["expected"][judge]
        actual, text = L.read_output(judge, results / case)
        status, detail = L.grade(judge, expected, actual, text,
                                 kind=exp.get("kind", "buggy"), flag_terms=exp.get("flag_terms") or [])
        rows.append({"case": case, "kind": exp.get("kind", "buggy"), "pattern": exp["pattern_id"],
                     "expected": expected, "actual": actual, "status": status, "detail": detail})
    report = L.render_report("failure-mode eval", judge, rows)
    print(report)
    print(L.verdict_explainer(rows))
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a") as fh:
            fh.write(report + "\n")
    if summary:
        L.write_summary(summary, SUITE, judge, rows)
    return L.exit_code(rows)


def lint() -> int:  # noqa: C901 — pre-existing, not a lint-floor refactor
    """Fixture invariants a model never touches. Run by the deterministic job."""
    problems = []
    for case in list_cases(None):
        d = CASES_DIR / case
        exp = load_expected(case)
        for name in ("diff.patch", "context.md", "notes.md"):
            if not (d / name).is_file():
                problems.append(f"{case}: missing {name}")
        ctx = (d / "context.md").read_text() if (d / "context.md").is_file() else ""
        for leak in ("Pattern:", "Reviewer note", "§", exp["pattern_id"]):
            if leak in ctx:
                problems.append(f"{case}: context.md leaks '{leak}'")
        kind = exp.get("kind", "buggy")
        sf, ft = exp.get("should_flag", []), exp.get("flag_terms", [])
        if kind == "buggy":
            if not sf:
                problems.append(f"{case}: buggy fixture with empty should_flag")
            if len(sf) != len(ft):
                problems.append(f"{case}: flag_terms ({len(ft)}) not parallel to should_flag ({len(sf)})")
            if exp["expected"] != {"code-judge": "fail", "founder-voice-pr-reviewer": "request-changes"}:
                problems.append(f"{case}: buggy fixture must expect fail/request-changes")
            desc = ctx.lower()
            for i, alts in enumerate(ft):
                for t in alts:
                    if t.lower() in desc:
                        problems.append(
                            f"{case}: flag_terms[{i}] '{t}' appears in context.md — "
                            "a reviewer echoing the description would score"
                        )
        else:
            if sf or ft:
                problems.append(f"{case}: control fixture must have empty should_flag/flag_terms")
            if exp["expected"] != {"code-judge": "pass", "founder-voice-pr-reviewer": "approve"}:
                problems.append(f"{case}: control fixture must expect pass/approve")
    controls = list_cases(None, kind="control")
    if len(controls) < 3:
        problems.append(f"only {len(controls)} control fixture(s); need at least 3")
    if problems:
        print("failure-mode fixture lint FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    n = len(list_cases(None))
    print(f"failure-mode fixture lint OK: {n} fixtures ({len(controls)} controls), no answer leaks in context.md")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["cases", "setup", "collect", "compare", "lint"])
    p.add_argument("--judge", choices=JUDGES)
    p.add_argument("--case")
    p.add_argument("--results", type=Path)
    p.add_argument("--only", help="comma-separated case subset")
    p.add_argument("--kind", choices=["buggy", "control"])
    p.add_argument("--summary", type=Path, help="write a JSON summary here (compare)")
    p.add_argument("--sandbox", type=Path, help="cwd to build for the judge (setup)")
    p.add_argument("--rubric", type=Path,
                   default=REPO / "internal-docs/07-engineering-docs/code-judge-rubric.md")
    args = p.parse_args()

    if args.command == "cases":
        print("\n".join(list_cases(args.only, args.kind)))
        return 0
    if args.command == "lint":
        return lint()
    if args.command == "setup":
        if not (args.case and args.judge):
            sys.exit("setup requires --case --judge")
        setup(args.case, args.judge, args.rubric, args.sandbox)
        return 0
    if args.command == "collect":
        if not (args.judge and args.case and args.results):
            sys.exit("collect requires --judge --case --results")
        collect(args.judge, args.case, args.results)
        return 0
    if not (args.judge and args.results):
        sys.exit("compare requires --judge --results")
    return compare(args.judge, args.results, args.only, args.summary)


if __name__ == "__main__":
    sys.exit(main())
