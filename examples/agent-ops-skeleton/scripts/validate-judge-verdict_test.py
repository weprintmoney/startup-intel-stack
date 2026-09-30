#!/usr/bin/env python3
"""Unit tests for scripts/validate-judge-verdict.py.

Stdlib-only (unittest); jsonschema must be importable, as in CI. Run:
`python3 scripts/validate-judge-verdict_test.py`.
"""

from __future__ import annotations

import importlib.util as _iu
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SPEC = _iu.spec_from_file_location("validate_judge_verdict", HERE / "validate-judge-verdict.py")
vjv = _iu.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(vjv)

SCRIPT = str(HERE / "validate-judge-verdict.py")
SCHEMA = str(HERE.parent / "schemas" / "judge-verdict.schema.json")


def good_verdict(n_fail: int = 2, n_na: int = 1, **over):
    """A consistent verdict: 20 criteria, first n_fail fail, next n_na n/a, rest pass."""
    crit = []
    for i, cid in enumerate(vjv.CRITERIA):
        if i < n_fail:
            crit.append({"id": cid, "result": "fail", "note": f"{cid} fails"})
        elif i < n_fail + n_na:
            crit.append({"id": cid, "result": "n/a"})
        else:
            crit.append({"id": cid, "result": "pass"})
    n_pass = 20 - n_fail - n_na
    score = vjv.round_half_up(100 * n_pass / (n_pass + n_fail)) if n_pass + n_fail else 0
    doc = {
        "judge": "code-judge",
        "repo": "example-org/example-app-sdk-py",
        "pr": 12,
        "verdict": "pass" if score >= 80 else "fail",
        "score": score,
        "threshold": 80,
        "criteria": crit,
        "blocking_findings": [],
        "rubric_version": "9f2c1ab",
        "model": "claude-opus-4-7",
        "run_url": "https://github.com/example-org/agent-ops/actions/runs/2",
        "created_at": "2026-09-12T02:00:00Z",
    }
    doc.update(over)
    return doc


def run_cli(doc, *flags):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(doc, f)
    return subprocess.run(
        [sys.executable, SCRIPT, f.name, "--schema", SCHEMA, *flags],
        capture_output=True, text=True,
    )


class Arithmetic(unittest.TestCase):
    def test_round_half_up(self):
        self.assertEqual(vjv.round_half_up(88.5), 89)
        self.assertEqual(vjv.round_half_up(94.4), 94)
        self.assertEqual(vjv.round_half_up(100 * 17 / 19), 89)


class AssessmentBadVerdict(unittest.TestCase):
    """The verdict the assessment says the old schema accepted."""

    def test_rejected_with_multiple_reasons(self):
        doc = good_verdict()
        doc["criteria"] = [{"id": "C01", "result": "pass"}]
        doc["score"] = 3
        doc["verdict"] = "pass"
        del doc["blocking_findings"]
        rep = vjv.validate(doc, SCHEMA, 80)
        self.assertFalse(rep["ok"])
        self.assertGreaterEqual(len(rep["errors"]), 3, rep["errors"])
        joined = "\n".join(rep["errors"])
        self.assertIn("missing C02", joined)
        self.assertIn("score: reported 3", joined)
        self.assertIn("blocking_findings: missing", joined)


class ConsistentVerdicts(unittest.TestCase):
    def test_pass_accepted(self):
        rep = vjv.validate(good_verdict(), SCHEMA, 80)
        self.assertTrue(rep["ok"], rep["errors"])
        self.assertEqual(rep["verdict"], "pass")
        self.assertEqual(rep["computed_score"], 89)

    def test_fail_accepted_when_consistent(self):
        rep = vjv.validate(good_verdict(n_fail=6, n_na=0), SCHEMA, 80)  # 14/20 = 70
        self.assertTrue(rep["ok"], rep["errors"])
        self.assertEqual(rep["verdict"], "fail")

    def test_off_by_one_score_tolerated(self):
        rep = vjv.validate(good_verdict(score=90), SCHEMA, 80)
        self.assertTrue(rep["ok"], rep["errors"])
        self.assertEqual(rep["computed_score"], 89)

    def test_fixture_is_valid(self):
        fixture = json.loads((HERE.parent / "schemas/fixtures/judge-verdict.example.json").read_text())
        rep = vjv.validate(fixture, SCHEMA, 80)
        self.assertTrue(rep["ok"], rep["errors"])


class Rejections(unittest.TestCase):
    def assert_rejected(self, doc, fragment, threshold=80):
        rep = vjv.validate(doc, SCHEMA, threshold)
        self.assertFalse(rep["ok"])
        self.assertTrue(any(fragment in e for e in rep["errors"]), f"{fragment!r} not in {rep['errors']}")
        return rep

    def test_score_off_by_more_than_one(self):
        self.assert_rejected(good_verdict(score=95), "recomputes to 89")

    def test_score_consistent_but_verdict_wrong(self):
        self.assert_rejected(good_verdict(verdict="fail"), "implies 'pass'")

    def test_blocking_finding_with_pass(self):
        rep = self.assert_rejected(
            good_verdict(blocking_findings=["B1: touches src/cpu/kernel.cpp"]), "implies 'fail'"
        )
        self.assertEqual(rep["verdict"], "fail")
        self.assertEqual(rep["blocking_findings_count"], 1)

    def test_all_na(self):
        doc = good_verdict(n_fail=0, n_na=20)
        doc["score"] = 100
        self.assert_rejected(doc, "no criterion judged")

    def test_missing_c13(self):
        doc = good_verdict()
        doc["criteria"] = [c for c in doc["criteria"] if c["id"] != "C13"]
        self.assert_rejected(doc, "missing C13")

    def test_duplicate_id(self):
        doc = good_verdict()
        doc["criteria"][19] = {"id": "C01", "result": "pass"}
        rep = self.assert_rejected(doc, "duplicate id C01")
        self.assertTrue(any("missing C20" in e for e in rep["errors"]))

    def test_wrong_threshold(self):
        self.assert_rejected(good_verdict(threshold=70), "rubric threshold is 80")

    def test_bad_result_word(self):
        doc = good_verdict()
        doc["criteria"][5]["result"] = "maybe"
        self.assert_rejected(doc, "not in pass|fail|n/a")

    def test_empty_blocking_string(self):
        self.assert_rejected(good_verdict(blocking_findings=[""], verdict="fail"), "not a non-empty string")


class Cli(unittest.TestCase):
    def test_json_shape_on_success(self):
        r = run_cli(good_verdict(), "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(
            set(out), {"ok", "verdict", "computed_score", "reported_score", "threshold",
                       "blocking_findings_count", "errors"},
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["computed_score"], 89)

    def test_json_still_printed_on_failure(self):
        r = run_cli(good_verdict(score=3), "--json")
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertFalse(out["ok"])
        self.assertEqual(out["verdict"], "pass")  # recomputed, not the reported word
        self.assertTrue(out["errors"])

    def test_text_mode(self):
        ok = run_cli(good_verdict())
        self.assertEqual(ok.returncode, 0)
        self.assertIn("valid: verdict=pass score=89 (reported 89) blocking=0", ok.stdout)
        bad = run_cli(good_verdict(threshold=70))
        self.assertEqual(bad.returncode, 1)
        self.assertIn("JUDGE VERDICT VALIDATION FAILED:", bad.stderr)

    def test_unparseable_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
        r = subprocess.run([sys.executable, SCRIPT, f.name, "--json"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertFalse(out["ok"])
        self.assertEqual(out["verdict"], "fail")


if __name__ == "__main__":
    unittest.main(verbosity=1)
