#!/usr/bin/env python3
"""Unit tests for evals/eval_lib.py — the deterministic half of the judge eval suites."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_lib as L  # noqa: E402


class Sandbox(unittest.TestCase):
    def test_neutral_run_url_hides_slug_and_is_stable(self):
        a = L.neutral_run_url("failure-mode-cases", "false-sharing-hot-cacheline")
        b = L.neutral_run_url("failure-mode-cases", "false-sharing-hot-cacheline")
        self.assertEqual(a, b)
        self.assertNotIn("false-sharing", a)
        self.assertNotEqual(a, L.neutral_run_url("failure-mode-cases", "write-skew-phantoms"))

    def test_sanitize_catalog_drops_fixture_pointers(self):
        cat = {"schema_version": 1, "entries": [
            {"id": "b", "signature": "s", "detection": {"static": ["x"], "fixture": "evals/failure-mode-cases/b/"}},
            {"id": "a", "signature": "s2", "detection": {"runtime": ["y"], "fixture": "evals/failure-mode-cases/a/"}}]}
        out = L.sanitize_catalog(cat)
        self.assertEqual([e["id"] for e in out["entries"]], ["a", "b"])
        self.assertNotIn("fixture", json.dumps(out))
        self.assertIn("signature", json.dumps(out))
        self.assertEqual(cat["entries"][0]["detection"]["fixture"], "evals/failure-mode-cases/b/")  # input untouched

    def test_make_sandbox_contains_only_catalog_and_schema(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "repo"
            (root / "state").mkdir(parents=True)
            (root / "schemas").mkdir()
            failure_modes = {"entries": [{"id": "x", "detection": {"fixture": "p"}}]}
            (root / "state" / "failure-modes.json").write_text(json.dumps(failure_modes))
            (root / "schemas" / "judge-verdict.schema.json").write_text("{}")
            (root / "evals").mkdir()
            (root / "evals" / "expected.json").write_text("{}")
            sb = L.make_sandbox(Path(d) / "sb", root)
            files = sorted(str(p.relative_to(sb)) for p in sb.rglob("*") if p.is_file())
            self.assertEqual(files, ["schemas/judge-verdict.schema.json", "state/failure-modes.json"])
            self.assertNotIn("fixture", (sb / "state" / "failure-modes.json").read_text())


class Reading(unittest.TestCase):
    def test_parse_verdict_line_variants(self):
        self.assertEqual(L.parse_verdict_line("VERDICT: approve\nbody"), "approve")
        self.assertEqual(L.parse_verdict_line("**VERDICT: request-changes**\n"), "request-changes")
        self.assertEqual(L.parse_verdict_line("`VERDICT: comment`"), "comment")
        self.assertEqual(L.parse_verdict_line("Looks good.\nVERDICT: approve"), "approve")
        self.assertIsNone(L.parse_verdict_line("no verdict here"))

    def test_read_code_judge_states(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            self.assertEqual(L.read_code_judge(p)[0], L.MISSING)
            (p / "verdict.json").write_text("{not json")
            self.assertEqual(L.read_code_judge(p)[0], L.MALFORMED)
            (p / "verdict.json").write_text(json.dumps({"verdict": "maybe"}))
            self.assertEqual(L.read_code_judge(p)[0], L.MALFORMED)
            verdict = {
                "verdict": "fail",
                "criteria": [{"id": "C08", "result": "fail", "note": "false sharing on WorkerStats"}],
                "blocking_findings": ["B2: x"],
            }
            (p / "verdict.json").write_text(json.dumps(verdict))
            (p / "findings.md").write_text("## code-judge: FAIL\nadd alignas(64)")
            v, text = L.read_code_judge(p)
            self.assertEqual(v, "fail")
            for s in ("false sharing", "alignas", "B2: x"):
                self.assertIn(s, text)

    def test_read_reviewer_states(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            self.assertEqual(L.read_reviewer(p)[0], L.MISSING)
            (p / "review.md").write_text("no verdict line")
            self.assertEqual(L.read_reviewer(p)[0], L.MALFORMED)
            (p / "review.md").write_text("VERDICT: comment\nLooks good, one nit.")
            self.assertEqual(L.read_reviewer(p)[0], "comment")


class Grading(unittest.TestCase):
    TERMS = [["false sharing", "same cacheline"], ["alignas", "padding"]]

    def test_match_when_verdict_and_a_callout_agree(self):
        result = L.grade("code-judge", "fail", "fail", "C08 fail: false sharing", "buggy", self.TERMS)
        self.assertEqual(result[0], L.MATCH)

    def test_wrong_reason_when_no_callout_evidenced(self):
        st, detail = L.grade("code-judge", "fail", "fail", "C18 fail: debug print left in", "buggy", self.TERMS)
        self.assertEqual(st, L.WRONG_REASON)
        self.assertIn("0/2", detail)

    def test_flip_when_verdict_differs(self):
        self.assertEqual(L.grade("code-judge", "fail", "pass", "false sharing", "buggy", self.TERMS)[0], L.FLIP)

    def test_missing_and_malformed_are_not_flips(self):
        self.assertEqual(L.grade("code-judge", "fail", L.MISSING, "", "buggy", self.TERMS)[0], L.MISSING)
        self.assertEqual(
            L.grade("founder-voice-pr-reviewer", "approve", L.MALFORMED, "", "control", [])[0], L.MALFORMED)

    def test_control_grades_verdict_only(self):
        self.assertEqual(L.grade("code-judge", "pass", "pass", "", "control", [])[0], L.MATCH)
        self.assertEqual(L.grade("code-judge", "pass", "fail", "false sharing", "control", [])[0], L.FLIP)

    def test_comment_is_non_blocking_for_reviewers(self):
        self.assertEqual(L.grade("founder-voice-pr-reviewer", "approve", "comment", "", "control", [])[0], L.MATCH)
        self.assertEqual(
            L.grade("founder-voice-pr-reviewer", "request-changes", "comment", "x", "buggy", [["x"]])[0], L.FLIP)

    def test_min_flagged(self):
        under = L.grade("code-judge", "fail", "fail", "false sharing", "buggy", self.TERMS, min_flagged=2)
        self.assertEqual(under[0], L.WRONG_REASON)
        over = L.grade(
            "code-judge", "fail", "fail", "false sharing; add padding", "buggy", self.TERMS, min_flagged=2
        )
        self.assertEqual(over[0], L.MATCH)

    def test_evidenced_is_case_insensitive_and_skips_empty_terms(self):
        self.assertEqual(L.evidenced("Add ALIGNAS(64) here", [["alignas"], ["", "nothing"]]), [True, False])


class Reports(unittest.TestCase):
    def rows(self):
        return [
            {"case": "a", "kind": "buggy", "expected": "fail", "actual": "fail", "status": L.MATCH, "detail": ""},
            {"case": "b", "kind": "buggy", "expected": "fail", "actual": "pass", "status": L.FLIP, "detail": ""},
            {
                "case": "c",
                "kind": "control",
                "expected": "pass",
                "actual": L.MISSING,
                "status": L.MISSING,
                "detail": "",
            },
        ]

    def test_counts_exit_and_explainer(self):
        rows = self.rows()
        c = L.counts(rows)
        self.assertEqual((c["total"], c[L.MATCH], c[L.FLIP], c[L.MISSING]), (3, 1, 1, 1))
        self.assertEqual(L.exit_code(rows), 1)
        self.assertEqual(L.exit_code(rows[:1]), 0)
        text = L.verdict_explainer(rows)
        self.assertIn("1 verdict flip", text)
        self.assertIn("NOT reviewer drift", text)
        rep = L.render_report("failure-mode eval", "code-judge", rows)
        self.assertIn("FAIL (1/3 match · 1 flip · 0 wrong-reason · 1 missing · 0 malformed)", rep)

    def test_write_summary(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s" / "summary.json"
            L.write_summary(p, "failure-mode-cases", "code-judge", self.rows())
            s = json.loads(p.read_text())
            self.assertEqual(s["counts"]["total"], 3)
            self.assertEqual(s["judge"], "code-judge")


class RepeatConsistency(unittest.TestCase):
    """Separating real miscalibration from run-to-run noise."""

    def test_every_run_matches_is_consistent_match(self):
        c = L.classify_consistency([L.MATCH, L.MATCH, L.MATCH])
        self.assertEqual(c["label"], L.CONSISTENT_MATCH)
        self.assertEqual(c["agreement_rate"], 1.0)
        self.assertEqual((c["match_runs"], c["usable_runs"]), (3, 3))

    def test_every_run_flips_is_consistent_disagree(self):
        c = L.classify_consistency([L.FLIP, L.FLIP, L.FLIP])
        self.assertEqual(c["label"], L.CONSISTENT_DISAGREE)
        self.assertEqual(c["agreement_rate"], 0.0)

    def test_mixed_runs_is_flips_across_runs_not_consistent_disagree(self):
        # The exact scenario the ticket names: slow-fp-denormals flipped once
        # but reproduced as a pass on immediate retry — noise, not a real signal.
        c = L.classify_consistency([L.FLIP, L.MATCH, L.MATCH])
        self.assertEqual(c["label"], L.FLIPS_ACROSS_RUNS)
        self.assertAlmostEqual(c["agreement_rate"], 2 / 3)

    def test_missing_and_malformed_runs_excluded_from_rate_not_counted_as_flip(self):
        c = L.classify_consistency([L.MATCH, L.MATCH, L.MISSING])
        self.assertEqual(c["label"], L.CONSISTENT_MATCH)
        self.assertEqual(c["usable_runs"], 2)
        self.assertEqual(c["total_runs"], 3)

    def test_all_runs_missing_is_inconclusive_not_consistent_disagree(self):
        c = L.classify_consistency([L.MISSING, L.MALFORMED])
        self.assertEqual(c["label"], L.INCONCLUSIVE)
        self.assertIsNone(c["agreement_rate"])
        self.assertEqual(c["usable_runs"], 0)

    def _rows(self):
        return [
            {"case": "a", "expected": "request-changes",
             "statuses": [L.MATCH, L.MATCH, L.MATCH],
             "classification": L.classify_consistency([L.MATCH, L.MATCH, L.MATCH])},
            {"case": "b", "expected": "approve",
             "statuses": [L.FLIP, L.FLIP, L.FLIP],
             "classification": L.classify_consistency([L.FLIP, L.FLIP, L.FLIP])},
            {"case": "c", "expected": "approve",
             "statuses": [L.FLIP, L.MATCH, L.FLIP],
             "classification": L.classify_consistency([L.FLIP, L.MATCH, L.FLIP])},
            {"case": "d", "expected": "approve",
             "statuses": [L.MISSING, L.MISSING, L.MISSING],
             "classification": L.classify_consistency([L.MISSING, L.MISSING, L.MISSING])},
        ]

    def test_breakdown_excludes_inconclusive_from_denominator(self):
        agg = L.consistency_rate_breakdown(self._rows())
        self.assertEqual(agg["total_cases"], 4)
        self.assertEqual(agg["conclusive_cases"], 3)
        self.assertEqual(agg["inconclusive_cases"], 1)
        self.assertEqual(agg["consistent_match"], 1)
        self.assertEqual(agg["consistent_disagree"], 1)
        self.assertEqual(agg["flips_across_runs"], 1)
        # 1 consistent-disagree / 3 conclusive cases — the headline this
        # ticket exists to separate from a single-run aggregate flip rate.
        self.assertAlmostEqual(agg["consistent_disagreement_rate"], 1 / 3)

    def test_breakdown_rate_is_none_when_every_case_is_inconclusive(self):
        rows = [{"case": "d", "expected": "approve", "statuses": [L.MISSING],
                 "classification": L.classify_consistency([L.MISSING])}]
        agg = L.consistency_rate_breakdown(rows)
        self.assertIsNone(agg["consistent_disagreement_rate"])
        self.assertEqual(agg["conclusive_cases"], 0)

    def test_render_repeat_report_names_every_case_and_the_headline_rate(self):
        report = L.render_repeat_report("founder-voice-pr-reviewer", 3, self._rows())
        self.assertIn("33%", report)  # headline consistent-disagreement rate
        for case in ("a", "b", "c", "d"):
            self.assertIn(f"| {case} |", report)
        self.assertIn(L.CONSISTENT_DISAGREE, report)
        self.assertIn(L.FLIPS_ACROSS_RUNS, report)
        self.assertIn(L.INCONCLUSIVE, report)

    def test_write_repeat_summary(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s" / "repeat-summary.json"
            L.write_repeat_summary(p, "pr-cases", "founder-voice-pr-reviewer", 3, self._rows())
            s = json.loads(p.read_text())
            self.assertEqual(s["runs"], 3)
            self.assertEqual(s["breakdown"]["conclusive_cases"], 3)
            self.assertEqual(len(s["cases"]), 4)


if __name__ == "__main__":
    unittest.main(verbosity=1)
