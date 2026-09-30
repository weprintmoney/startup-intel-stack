#!/usr/bin/env python3
"""Deterministic gate on miner output: schema conformance, score arithmetic,
and verdict/threshold consistency. The model's arithmetic is never trusted.

Usage: validate-release-findings.py <findings.json> [--schema schemas/release-findings.schema.json]
Exit 0 = valid; exit 1 = invalid (reasons on stderr).
"""
import json
import sys
from pathlib import Path

DIMENSIONS = [
    "icp_problem_match",
    "messaging_alignment",
    "market_resonance",
    "differentiation_delta",
    "template_impact",
]


def main() -> int:  # noqa: C901 — pre-existing, not a lint-floor refactor
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 1
    findings_path = args[0]
    schema_path = "schemas/release-findings.schema.json"
    if "--schema" in args:
        schema_path = args[args.index("--schema") + 1]

    errors = []
    try:
        doc = json.loads(Path(findings_path).read_text())
    except Exception as e:
        print(f"ERROR: {findings_path}: unparseable JSON — {e}", file=sys.stderr)
        return 1

    try:
        from jsonschema import Draft202012Validator, FormatChecker

        schema = json.loads(Path(schema_path).read_text())
        v = Draft202012Validator(schema, format_checker=FormatChecker())
        for e in sorted(v.iter_errors(doc), key=lambda e: e.json_path):
            errors.append(f"schema: {e.json_path}: {e.message}")
    except ImportError:
        errors.append("jsonschema not installed — schema check skipped is a hard error in CI")

    threshold = doc.get("market_worthy_min")
    for i, f in enumerate(doc.get("findings", [])):
        scores = f.get("scores", {})
        if sorted(scores) == sorted(DIMENSIONS):
            computed = sum(scores[d] for d in DIMENSIONS)
            if f.get("total") != computed:
                errors.append(
                    f"findings[{i}] (PR #{f.get('pr_number')}): total={f.get('total')} but sum(scores)={computed}"
                )
            if isinstance(threshold, int):
                expected = "market-worthy" if computed >= threshold else "not-market-worthy"
                if f.get("verdict") != expected:
                    errors.append(
                        f"findings[{i}] (PR #{f.get('pr_number')}): verdict={f.get('verdict')} "
                        f"but sum {computed} vs threshold {threshold} implies {expected}"
                    )
        if f.get("verdict") == "market-worthy" and not f.get("evidence"):
            errors.append(f"findings[{i}] (PR #{f.get('pr_number')}): market-worthy with no evidence")

    if errors:
        print("RELEASE FINDINGS VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    worthy = sum(1 for f in doc.get("findings", []) if f.get("verdict") == "market-worthy")
    print(f"valid: {len(doc.get('findings', []))} findings, {worthy} market-worthy, threshold {threshold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
