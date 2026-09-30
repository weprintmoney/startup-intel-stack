#!/usr/bin/env python3
"""Golden-set eval harness for the PR reviewers (evals/pr-cases/).

Fixtures are historical PRs with known human verdicts (MINING-REPORT.md):
diff.patch + context.md + expected.json. The harness runs the UNMODIFIED
production prompt against each case; a verdict flip means the reviewer
drifted (prompt edit, rubric edit in internal-docs, model change).

Honest-eval design:
  * each case names the human `reviewer` who produced the verdict and the
    `graded_by` list of judges it is a valid golden for. A persona graded
    against another author's habits measures style mismatch, not review
    quality: founder-voice-pr-reviewer is
    graded on the founder's reviews plus author-neutral clean approvals; the generic
    pr-reviewer on engineers' change requests plus the same
    clean approvals; code-judge on everything.
  * the rubric is staged for code-judge only — production reviewers never
    see one; context.md is the spec stand-in they do see.
  * run_url no longer spells the case slug; the judge runs with cwd = a
    sandbox (--sandbox) so it cannot read expected.json.
  * `VERDICT: comment` (the founder's COMMENTED — non-blocking) grades as approve
; MISSING/MALFORMED are reported apart from FLIP.

Per-case flow (driven by .github/workflows/judge-evals.yml):
  run_eval.py cases   [--only a,b] [--judge J]
  run_eval.py setup   --case SLUG --judge J [--rubric PATH] [--sandbox DIR]
  <workflow runs: (cd SANDBOX && claude -p agents/<judge>/CLAUDE.md ...)>
  run_eval.py collect --judge J --case SLUG --results DIR
  run_eval.py compare --judge J --results DIR [--only a,b] [--summary PATH]
  run_eval.py lint    # fixture invariants, no model (deterministic job)

Repeat-run consistency (driven by
.github/workflows/judge-evals-repeat.yml, dispatch-only, additive to the
single-run baseline above): the workflow loops `setup`/`collect` N times per
case, writing each run's collected output to `<results-base>/run-<i>/<case>/`
(same shape `collect --results DIR` always wrote, one `DIR` per run index),
then:
  run_eval.py repeat-compare --judge J --results-base DIR --runs N
      [--only a,b] [--summary PATH]
Classifies each case as `consistent_match` (every run agrees with history),
`consistent_disagree` (every run disagrees — a real calibration signal, not
noise), `flips_across_runs` (some runs agree, some don't — sampling noise),
or `inconclusive` (every run MISSING/MALFORMED — infra, not a verdict).
Diagnostic only: always exits 0, never gates a merge.
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
SUITE = "pr-cases"
CASES_DIR = REPO / "evals" / SUITE
REVIEW_INPUT = Path("/tmp/review-input")
REVIEW_OUTPUT = Path("/tmp/review-output")
JUDGES = ("code-judge", "founder-voice-pr-reviewer", "pr-reviewer")


def load_expected(case: str) -> dict:
    return json.loads((CASES_DIR / case / "expected.json").read_text())


def list_cases(only: str | None, judge: str | None = None) -> list[str]:
    slugs = sorted(d.name for d in CASES_DIR.iterdir() if (d / "expected.json").is_file())
    if judge:
        default_graders = ["code-judge", "founder-voice-pr-reviewer"]
        slugs = [s for s in slugs if judge in load_expected(s).get("graded_by", default_graders)]
    if only:
        wanted = [s.strip() for s in only.split(",") if s.strip()]
        missing = [w for w in wanted if w not in slugs]
        if missing:
            sys.exit(f"unknown or not-graded case(s) for {judge or 'any judge'}: {', '.join(missing)}")
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
    shutil.copy(src / "diff.patch", REVIEW_INPUT / "diff.patch")
    shutil.copy(src / "context.md", REVIEW_INPUT / "context.md")
    if judge == "code-judge":
        if not rubric.is_file():
            sys.exit(f"rubric not found at {rubric} — the workflow must check out internal-docs first")
        shutil.copy(rubric, REVIEW_INPUT / "rubric.md")
    exp = load_expected(case)
    (REVIEW_INPUT / "run-meta.json").write_text(json.dumps({
        "repo": exp["repo"],
        "pr": exp["pr"],
        "rubric_version": "eval-golden-set",
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
    for case in list_cases(only, judge):
        exp = load_expected(case)
        expected = exp["expected"][judge]
        actual, text = L.read_output(judge, results / case)
        status, detail = L.grade(judge, expected, actual, text, kind="golden", flag_terms=None)
        score = "-"
        vf = results / case / "verdict.json"
        if judge == "code-judge" and vf.is_file():
            try:
                score = str(json.loads(vf.read_text()).get("score", "-"))
            except json.JSONDecodeError:
                pass
        rows.append({"case": case, "kind": exp.get("reviewer", ""), "expected": expected, "actual": actual,
                     "status": status, "detail": f"score {score}" if judge == "code-judge" else detail})
    report = L.render_report("golden-set eval", judge, rows)
    print(report)
    print(L.verdict_explainer(rows))
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a") as fh:
            fh.write(report + "\n")
    if summary:
        L.write_summary(summary, SUITE, judge, rows)
    return L.exit_code(rows)


def repeat_compare(judge: str, results_base: Path, runs: int, only: str | None, summary: Path | None) -> int:
    """Grade every case `runs` times (results staged by the
    workflow at `results_base/run-<i>/<case>/...`, same shape `collect`
    already writes per run) and classify each case's agreement across runs
    instead of a single pass/fail. Diagnostic, not a merge gate — additive
    to `compare`'s single-run baseline, never replaces it, so it always
    exits 0 (an infra MISSING/MALFORMED run still shows up in the table and
    can drag a case to `inconclusive`, but it never fails the build)."""
    rows = []
    for case in list_cases(only, judge):
        exp = load_expected(case)
        expected = exp["expected"][judge]
        statuses = []
        for i in range(1, runs + 1):
            actual, text = L.read_output(judge, results_base / f"run-{i}" / case)
            status, _ = L.grade(judge, expected, actual, text, kind="golden", flag_terms=None)
            statuses.append(status)
        rows.append({"case": case, "kind": exp.get("reviewer", ""), "expected": expected,
                     "statuses": statuses, "classification": L.classify_consistency(statuses)})
    report = L.render_repeat_report(judge, runs, rows)
    print(report)
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a") as fh:
            fh.write(report + "\n")
    if summary:
        L.write_repeat_summary(summary, SUITE, judge, runs, rows)
    return 0


def lint() -> int:  # noqa: C901 — pre-existing, not a lint-floor refactor
    problems = []
    for case in list_cases(None):
        exp = load_expected(case)
        d = CASES_DIR / case
        for name in ("diff.patch", "context.md"):
            if not (d / name).is_file():
                problems.append(f"{case}: missing {name}")
        if not exp.get("reviewer"):
            problems.append(f"{case}: no `reviewer` (who produced the human verdict)")
        gb = exp.get("graded_by") or []
        if "code-judge" not in gb:
            problems.append(f"{case}: code-judge must be in graded_by")
        for j in gb:
            if j not in JUDGES:
                problems.append(f"{case}: unknown judge in graded_by: {j}")
            if j not in exp.get("expected", {}):
                problems.append(f"{case}: graded_by names {j} but expected has no verdict for it")
        for j, v in exp.get("expected", {}).items():
            ok = {"code-judge": ("pass", "fail")}.get(j, ("approve", "request-changes"))
            if v not in ok:
                problems.append(f"{case}: expected[{j}]={v!r} not in {ok}")
    per_judge = {j: len(list_cases(None, j)) for j in JUDGES}
    # A real golden set wants 5+ graded cases per judge; the skeleton ships one
    # toy fixture, so the workflow lowers the floor via MIN_GRADED_CASES until you
    # have built your own corpus.
    min_graded = int(os.environ.get("MIN_GRADED_CASES", "5"))
    for j, n in per_judge.items():
        if n < min_graded:
            problems.append(f"{j}: only {n} graded case(s); the corpus is too thin to call drift")
    if problems:
        print("pr-cases fixture lint FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("pr-cases fixture lint OK: " + ", ".join(f"{j} graded on {n}" for j, n in per_judge.items()))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["cases", "setup", "collect", "compare", "repeat-compare", "lint"])
    p.add_argument("--judge", choices=JUDGES)
    p.add_argument("--case")
    p.add_argument("--results", type=Path)
    p.add_argument("--results-base", type=Path, help="repeat-compare: parent of run-<i>/<case>/ dirs")
    p.add_argument("--runs", type=int, help="repeat-compare: repeats per case")
    p.add_argument("--only", help="comma-separated case subset")
    p.add_argument("--summary", type=Path)
    p.add_argument("--sandbox", type=Path)
    p.add_argument("--rubric", type=Path,
                   default=REPO / "internal-docs/07-engineering-docs/code-judge-rubric.md")
    args = p.parse_args()

    if args.command == "cases":
        print("\n".join(list_cases(args.only, args.judge)))
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
    if args.command == "repeat-compare":
        if not (args.judge and args.results_base and args.runs):
            sys.exit("repeat-compare requires --judge --results-base --runs")
        return repeat_compare(args.judge, args.results_base, args.runs, args.only, args.summary)
    if not (args.judge and args.results):
        sys.exit("compare requires --judge --results")
    return compare(args.judge, args.results, args.only, args.summary)


if __name__ == "__main__":
    sys.exit(main())
