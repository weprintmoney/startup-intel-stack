#!/usr/bin/env python3
"""Shared grading for the judge eval suites.

Both runners (run_eval.py for pr-cases, run_failure_mode_eval.py for
failure-mode-cases) used to grade a single verdict bit and count every
infrastructure failure as a reviewer "flip". This module
is the one place that decides:

  * what the reviewer sandbox may see (make_sandbox: a sanitized
    failure-mode catalog and the verdict schema, nothing else — the judge runs
    with cwd here so it cannot grep expected.json or fixture directories);
  * a neutral run_url that no longer spells the pattern name;
  * how a reviewer's output is read (code-judge verdict.json + findings.md;
    reviewer review.md with VERDICT: approve|comment|request-changes, where
    `comment` is non-blocking and grades as approve — the COMMENTED state
    the founder actually uses most);
  * the status of one case: MATCH, FLIP (verdict wrong), WRONG_REASON
    (verdict right but none of the expected callouts is evidenced in the
    text — grading on should_flag via flag_terms), MISSING (no output
    file — infrastructure, never a reviewer flip), MALFORMED (unreadable).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

MATCH, FLIP, WRONG_REASON, MISSING, MALFORMED = "MATCH", "FLIP", "WRONG_REASON", "MISSING", "MALFORMED"
REVIEWER_VERDICTS = ("approve", "comment", "request-changes")


# ------------------------------------------------------------- sandbox ----

def neutral_run_url(suite: str, slug: str) -> str:
    """A stable per-case URL that does not spell the slug."""
    h = hashlib.sha1(f"{suite}/{slug}".encode()).hexdigest()[:8]
    return f"https://github.com/example-org/agent-ops/evals/{suite}/case-{h}"


def sanitize_catalog(catalog: dict) -> dict:
    """The failure-mode catalog without the fields that point at fixtures.

    Production judges may cite catalog pattern IDs; in an eval the catalog's
    `detection.fixture` path IS the answer key. Keep signatures and
    references, drop fixture pointers, order by id so nothing about the run
    order leaks either.
    """
    out = {k: v for k, v in catalog.items() if k != "entries"}
    entries = []
    for e in catalog.get("entries", []):
        e2 = json.loads(json.dumps(e))
        det = e2.get("detection")
        if isinstance(det, dict):
            det.pop("fixture", None)
        entries.append(e2)
    out["entries"] = sorted(entries, key=lambda e: e.get("id", ""))
    return out


def make_sandbox(sandbox: Path, repo_root: Path) -> Path:
    """cwd for an eval judge: sanitized catalog + verdict schema, nothing else."""
    if sandbox.exists():
        shutil.rmtree(sandbox)
    (sandbox / "state").mkdir(parents=True)
    (sandbox / "schemas").mkdir(parents=True)
    cat = repo_root / "state" / "failure-modes.json"
    if cat.is_file():
        (sandbox / "state" / "failure-modes.json").write_text(
            json.dumps(sanitize_catalog(json.loads(cat.read_text())), indent=2) + "\n")
    schema = repo_root / "schemas" / "judge-verdict.schema.json"
    if schema.is_file():
        shutil.copy(schema, sandbox / "schemas" / "judge-verdict.schema.json")
    return sandbox


# ------------------------------------------------------------- reading ----

_WRAP = re.compile(r"[`*]")


def parse_verdict_line(text: str) -> str | None:
    """First `VERDICT: <value>` line of a review, markdown wrappers tolerated."""
    for raw in text.splitlines():
        line = _WRAP.sub("", raw).strip().strip("_").strip()
        m = re.match(r"^VERDICT:\s*([A-Za-z-]+)", line)
        if m:
            return m.group(1).lower()
    return None


def read_code_judge(case_dir: Path) -> tuple[str, str]:
    """-> (verdict or status, evidence text)."""
    f = case_dir / "verdict.json"
    if not f.is_file():
        return MISSING, ""
    try:
        v = json.loads(f.read_text())
    except json.JSONDecodeError:
        return MALFORMED, ""
    verdict = v.get("verdict")
    if verdict not in ("pass", "fail"):
        return MALFORMED, ""
    parts = []
    findings = case_dir / "findings.md"
    if findings.is_file():
        parts.append(findings.read_text())
    for c in v.get("criteria", []) or []:
        if isinstance(c, dict) and c.get("note"):
            parts.append(str(c["note"]))
    parts += [str(b) for b in (v.get("blocking_findings") or [])]
    return verdict, "\n".join(parts)


def read_reviewer(case_dir: Path) -> tuple[str, str]:
    f = case_dir / "review.md"
    if not f.is_file():
        return MISSING, ""
    text = f.read_text()
    verdict = parse_verdict_line(text)
    if verdict not in REVIEWER_VERDICTS:
        return MALFORMED, text
    return verdict, text


def read_output(judge: str, case_dir: Path) -> tuple[str, str]:
    return read_code_judge(case_dir) if judge == "code-judge" else read_reviewer(case_dir)


def normalize(judge: str, verdict: str) -> str:
    """`comment` is a non-blocking review: for pass/fail grading it is approve."""
    if judge != "code-judge" and verdict == "comment":
        return "approve"
    return verdict


# ------------------------------------------------------------- grading ----

def evidenced(text: str, flag_terms: list[list[str]]) -> list[bool]:
    low = text.lower()
    return [any(t.lower() in low for t in alts if t) for alts in flag_terms]


def grade(judge: str, expected: str, actual: str, text: str,
          kind: str = "buggy", flag_terms: list[list[str]] | None = None,
          min_flagged: int = 1) -> tuple[str, str]:
    """-> (status, detail). expected is the golden verdict for this judge."""
    if actual in (MISSING, MALFORMED):
        return actual, "no usable output"
    if normalize(judge, actual) != normalize(judge, expected):
        return FLIP, f"expected {expected}, got {actual}"
    if kind == "control" or not flag_terms:
        return MATCH, "verdict matches" if kind == "control" else "verdict matches (no callouts to check)"
    hits = evidenced(text, flag_terms)
    n = sum(hits)
    if n < min_flagged:
        return WRONG_REASON, f"verdict matches but 0/{len(flag_terms)} expected callouts evidenced"
    return MATCH, f"{n}/{len(flag_terms)} callouts evidenced"


# ------------------------------------------------------ repeat-run consistency ----
#
# A single golden-set run conflates two different signals into one flip
# count: a judge genuinely miscalibrated against the historical verdict, and
# a judge that just landed on the wrong side of ordinary Opus run-to-run
# sampling variance for one case (several flips
# reproduced as a clean pass on an immediate retry against identical code).
# Grading a case N times and classifying its statuses
# across runs separates the two instead of reporting one aggregate rate.

CONSISTENT_MATCH = "consistent_match"
CONSISTENT_DISAGREE = "consistent_disagree"
FLIPS_ACROSS_RUNS = "flips_across_runs"
INCONCLUSIVE = "inconclusive"


def classify_consistency(statuses: list[str]) -> dict:
    """-> classification for one case's N repeat-run grading statuses.

    MISSING/MALFORMED runs are infrastructure noise, never a verdict (same
    rule as `grade`) — excluded from the agreement rate; a case is only
    `inconclusive` when EVERY run was infrastructure noise.
    """
    usable = [s for s in statuses if s not in (MISSING, MALFORMED)]
    if not usable:
        return {"label": INCONCLUSIVE, "agreement_rate": None, "usable_runs": 0,
                "match_runs": 0, "total_runs": len(statuses)}
    match_runs = sum(1 for s in usable if s == MATCH)
    n = len(usable)
    if match_runs == n:
        label = CONSISTENT_MATCH
    elif match_runs == 0:
        label = CONSISTENT_DISAGREE
    else:
        label = FLIPS_ACROSS_RUNS
    return {"label": label, "agreement_rate": match_runs / n, "usable_runs": n,
            "match_runs": match_runs, "total_runs": len(statuses)}


def consistency_rate_breakdown(rows: list[dict]) -> dict:
    """Aggregate across cases. `inconclusive` cases (every run missing/malformed)
    are excluded from `conclusive_cases` and from the disagreement rate — they
    are an infrastructure gap, not evidence either way."""
    conclusive = [r for r in rows if r["classification"]["label"] != INCONCLUSIVE]
    n = len(conclusive)
    consistent_match = sum(1 for r in conclusive if r["classification"]["label"] == CONSISTENT_MATCH)
    consistent_disagree = sum(1 for r in conclusive if r["classification"]["label"] == CONSISTENT_DISAGREE)
    flips = sum(1 for r in conclusive if r["classification"]["label"] == FLIPS_ACROSS_RUNS)
    return {
        "total_cases": len(rows),
        "conclusive_cases": n,
        "inconclusive_cases": len(rows) - n,
        "consistent_match": consistent_match,
        "consistent_disagree": consistent_disagree,
        "flips_across_runs": flips,
        "consistent_disagreement_rate": (consistent_disagree / n) if n else None,
    }


def render_repeat_report(judge: str, runs: int, rows: list[dict]) -> str:
    agg = consistency_rate_breakdown(rows)
    rate = agg["consistent_disagreement_rate"]
    rate_str = f"{rate:.0%}" if rate is not None else "n/a"
    head = (f"## {judge} repeat-run consistency ({runs}x/case) — "
            f"consistent-disagreement rate {rate_str} "
            f"({agg['consistent_disagree']}/{agg['conclusive_cases']} conclusive cases; "
            f"{agg['consistent_match']} consistent-match, {agg['flips_across_runs']} flip-across-runs, "
            f"{agg['inconclusive_cases']} inconclusive)")
    table = ["| case | expected | per-run statuses | classification | agreement |", "|---|---|---|---|---|"]
    for r in rows:
        c = r["classification"]
        if c["agreement_rate"] is None:
            rate_cell = "n/a"
        else:
            rate_cell = f"{c['agreement_rate']:.0%} ({c['match_runs']}/{c['usable_runs']})"
        table.append(f"| {r['case']} | {r['expected']} | {', '.join(r['statuses'])} | {c['label']} | {rate_cell} |")
    return head + "\n\n" + "\n".join(table) + "\n"


def write_repeat_summary(path: Path, suite: str, judge: str, runs: int, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {"suite": suite, "judge": judge, "runs": runs,
               "breakdown": consistency_rate_breakdown(rows), "cases": rows}
    path.write_text(json.dumps(summary, indent=2) + "\n")


# ------------------------------------------------------------- reports ----

def counts(rows: list[dict]) -> dict:
    c = {s: 0 for s in (MATCH, FLIP, WRONG_REASON, MISSING, MALFORMED)}
    for r in rows:
        c[r["status"]] = c.get(r["status"], 0) + 1
    c["total"] = len(rows)
    return c


def render_report(title: str, judge: str, rows: list[dict]) -> str:
    c = counts(rows)
    ok = c[FLIP] == 0 and c[WRONG_REASON] == 0 and c[MISSING] == 0 and c[MALFORMED] == 0
    head = (f"## {judge} {title} — {'PASS' if ok else 'FAIL'} "
            f"({c[MATCH]}/{c['total']} match · {c[FLIP]} flip · {c[WRONG_REASON]} wrong-reason · "
            f"{c[MISSING]} missing · {c[MALFORMED]} malformed)")
    table = ["| case | kind | expected | actual | status | detail |", "|---|---|---|---|---|---|"]
    table += [f"| {r['case']} | {r.get('kind','')} | {r['expected']} | {r['actual']} | {r['status']} | {r['detail']} |"
              for r in rows]
    return head + "\n\n" + "\n".join(table) + "\n"


def write_summary(path: Path, suite: str, judge: str, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {"suite": suite, "judge": judge, "counts": counts(rows), "cases": rows}
    path.write_text(json.dumps(summary, indent=2) + "\n")


def exit_code(rows: list[dict]) -> int:
    c = counts(rows)
    return 1 if (c[FLIP] or c[WRONG_REASON] or c[MISSING] or c[MALFORMED]) else 0


def verdict_explainer(rows: list[dict]) -> str:
    c = counts(rows)
    bits = []
    if c[FLIP]:
        bits.append(
            f"{c[FLIP]} verdict flip(s) — the reviewer disagrees with the golden verdict "
            "(reviewer drift, or the fixture is wrong)"
        )
    if c[WRONG_REASON]:
        bits.append(
            f"{c[WRONG_REASON]} wrong-reason — right verdict, but none of the expected "
            "callouts appears in the findings"
        )
    if c[MISSING] or c[MALFORMED]:
        bits.append(
            f"{c[MISSING] + c[MALFORMED]} missing/malformed — infrastructure or "
            "prompt-shape, NOT reviewer drift"
        )
    return "; ".join(bits) if bits else "all cases match"
