#!/usr/bin/env python3
"""Deterministic gate on the code-judge output: schema conformance, criterion
coverage, score arithmetic, and verdict/threshold consistency. The model's
arithmetic and its verdict word are never trusted -- both are recomputed from
the per-criterion results, exactly as the rubric defines them:

    score   = round(100 * pass / (pass + fail))     # n/a excluded, half-up
    verdict = pass  iff  score >= threshold AND blocking_findings is empty

Every check runs and every failure is reported (not first-fail), so one
rejected verdict tells the human everything that was wrong with it.

Usage:
  validate-judge-verdict.py <verdict.json> [--schema schemas/judge-verdict.schema.json]
                            [--threshold 80] [--json]

Exit 0 = valid; exit 1 = invalid. Text mode prints the reasons to stderr.
--json prints one object to stdout, {ok, verdict, computed_score,
reported_score, threshold, blocking_findings_count, errors}, in both cases
(so a workflow can read the recomputed verdict even when the file is
rejected) and still exits 1 when not ok.
"""
from __future__ import annotations

import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CRITERIA = [f"C{i:02d}" for i in range(1, 21)]
RESULTS = ("pass", "fail", "n/a")
DEFAULT_SCHEMA = "schemas/judge-verdict.schema.json"
DEFAULT_THRESHOLD = 80


def round_half_up(x: float) -> int:
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def validate(  # noqa: C901 — pre-existing, not a lint-floor refactor
    doc: dict, schema_path: str, threshold: int,
) -> dict:
    """Return the report dict; `ok` is False when any check fails."""
    errors: list[str] = []

    # (a) schema
    try:
        from jsonschema import Draft202012Validator, FormatChecker

        schema = json.loads(Path(schema_path).read_text())
        v = Draft202012Validator(schema, format_checker=FormatChecker())
        for e in sorted(v.iter_errors(doc), key=lambda e: e.json_path):
            errors.append(f"schema: {e.json_path}: {e.message}")
    except ImportError:
        errors.append("jsonschema not installed — schema check skipped is a hard error in CI")
    except FileNotFoundError:
        errors.append(f"schema file not found: {schema_path}")

    criteria = doc.get("criteria")
    if not isinstance(criteria, list):
        criteria = []
        errors.append("criteria: missing or not a list")

    # (b) exactly C01..C20, each once
    ids = [c.get("id") if isinstance(c, dict) else None for c in criteria]
    seen: set[str] = set()
    for cid in ids:
        if cid in seen:
            errors.append(f"criteria: duplicate id {cid}")
        seen.add(cid)
    missing = [c for c in CRITERIA if c not in seen]
    extra = sorted(c for c in seen if c not in CRITERIA)
    if missing:
        errors.append(f"criteria: missing {', '.join(missing)}")
    if extra:
        errors.append(f"criteria: unknown ids {', '.join(str(c) for c in extra)}")

    # (c) results
    n_pass = n_fail = 0
    for c in criteria:
        if not isinstance(c, dict):
            errors.append("criteria: entry is not an object")
            continue
        r = c.get("result")
        if r not in RESULTS:
            errors.append(f"criteria[{c.get('id')}]: result {r!r} not in pass|fail|n/a")
        elif r == "pass":
            n_pass += 1
        elif r == "fail":
            n_fail += 1

    # (d, e) arithmetic
    computed: int | None = None
    if n_pass + n_fail == 0:
        errors.append("no criterion judged (all n/a) — a verdict needs at least one pass or fail")
    else:
        computed = round_half_up(100 * n_pass / (n_pass + n_fail))
        reported = doc.get("score")
        if not isinstance(reported, (int, float)) or isinstance(reported, bool):
            errors.append(f"score: {reported!r} is not a number")
        elif abs(reported - computed) > 1:
            errors.append(
                f"score: reported {reported} but {n_pass} pass / {n_fail} fail recomputes to {computed}"
            )

    # (f) threshold
    if doc.get("threshold") != threshold:
        errors.append(f"threshold: {doc.get('threshold')!r} but the rubric threshold is {threshold}")

    # (g) blocking findings
    blocking = doc.get("blocking_findings")
    if blocking is None:
        errors.append("blocking_findings: missing (must be present, [] when none)")
        blocking = []
    elif not isinstance(blocking, list):
        errors.append("blocking_findings: not a list")
        blocking = []
    else:
        for i, b in enumerate(blocking):
            if not isinstance(b, str) or not b.strip():
                errors.append(f"blocking_findings[{i}]: not a non-empty string")

    # (h) verdict
    expected = None
    if computed is not None:
        expected = "pass" if (computed >= threshold and len(blocking) == 0) else "fail"
        if doc.get("verdict") != expected:
            why = f"score {computed} vs threshold {threshold}"
            if blocking:
                why += f", {len(blocking)} blocking finding(s)"
            errors.append(f"verdict: reported {doc.get('verdict')!r} but {why} implies {expected!r}")

    return {
        "ok": not errors,
        "verdict": expected if expected is not None else "fail",
        "computed_score": computed,
        "reported_score": doc.get("score"),
        "threshold": threshold,
        "blocking_findings_count": len(blocking),
        "errors": errors,
    }


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print(__doc__, file=sys.stderr)
        return 1
    path = args[0]
    schema_path = DEFAULT_SCHEMA
    threshold = DEFAULT_THRESHOLD
    as_json = "--json" in args
    if "--schema" in args:
        schema_path = args[args.index("--schema") + 1]
    if "--threshold" in args:
        threshold = int(args[args.index("--threshold") + 1])

    try:
        doc = json.loads(Path(path).read_text())
        if not isinstance(doc, dict):
            raise ValueError("top level is not an object")
    except Exception as e:  # unparseable input is one error, reported the same way
        report = {
            "ok": False, "verdict": "fail", "computed_score": None, "reported_score": None,
            "threshold": threshold, "blocking_findings_count": 0,
            "errors": [f"{path}: unparseable JSON — {e}"],
        }
    else:
        report = validate(doc, schema_path, threshold)

    if as_json:
        print(json.dumps(report))
    elif report["ok"]:
        print(
            f"valid: verdict={report['verdict']} score={report['computed_score']} "
            f"(reported {report['reported_score']}) blocking={report['blocking_findings_count']}"
        )
    else:
        print("JUDGE VERDICT VALIDATION FAILED:", file=sys.stderr)
        for e in report["errors"]:
            print(f"  - {e}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
