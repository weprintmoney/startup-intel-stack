#!/usr/bin/env python3
"""Unit tests for scripts/heartbeat.py."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import heartbeat as hb  # noqa: E402

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


def run_at(hours_ago: float) -> dict:
    ts = (NOW - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")
    return {"conclusion": "success", "created_at": ts, "html_url": "https://x/run"}


class TestEvaluateRuns(unittest.TestCase):
    def test_error_sentinel_is_a_warning_not_a_problem(self):
        problems, warnings = hb.evaluate_runs("wf.yml", 24, {"error": "boom"}, NOW)
        self.assertEqual(problems, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("could not read run history (boom)", warnings[0])

    def test_no_runs_scheduled_workflow_is_a_problem(self):
        problems, warnings = hb.evaluate_runs("wf.yml", 24, [], NOW)
        self.assertEqual(warnings, [])
        self.assertIn("no completed runs found at all", problems[0])

    def test_no_runs_on_demand_workflow_is_fine(self):
        problems, warnings = hb.evaluate_runs("wf.yml", None, [], NOW)
        self.assertEqual(problems, [])
        self.assertEqual(warnings, [])

    def test_latest_failed_is_a_problem(self):
        runs = [{"conclusion": "failure", "html_url": "https://x/1"}, run_at(1)]
        problems, _ = hb.evaluate_runs("wf.yml", 24, runs, NOW)
        self.assertTrue(any("latest run concluded *failure*" in p for p in problems))

    def test_latest_skipped_is_not_a_problem(self):
        runs = [{"conclusion": "skipped", "html_url": "https://x/1"}, run_at(1)]
        problems, _ = hb.evaluate_runs("wf.yml", 24, runs, NOW)
        self.assertEqual(problems, [])

    def test_on_demand_only_checks_latest_failure(self):
        # max_age=None: no successful-run/staleness check at all, even if
        # the only run ever is a failure and nothing else.
        runs = [{"conclusion": "failure", "html_url": "https://x/1"}]
        problems, _ = hb.evaluate_runs("wf.yml", None, runs, NOW)
        self.assertEqual(len(problems), 1)
        self.assertIn("latest run concluded", problems[0])

    def test_no_successful_run_at_all_is_a_problem(self):
        runs = [{"conclusion": "failure", "html_url": "https://x/1"}] * 3
        problems, _ = hb.evaluate_runs("wf.yml", 24, runs, NOW)
        self.assertTrue(any("no successful run in the last 3 completed runs" in p for p in problems))

    def test_stale_success_is_a_problem(self):
        runs = [run_at(30)]
        problems, _ = hb.evaluate_runs("wf.yml", 24, runs, NOW)
        self.assertTrue(any("last successful run was 30h ago" in p for p in problems))

    def test_fresh_success_is_healthy(self):
        runs = [run_at(1)]
        problems, _ = hb.evaluate_runs("wf.yml", 24, runs, NOW)
        self.assertEqual(problems, [])

    def test_exactly_at_boundary_is_not_stale(self):
        runs = [run_at(24)]
        problems, _ = hb.evaluate_runs("wf.yml", 24, runs, NOW)
        self.assertEqual(problems, [])


class TestPauseGated(unittest.TestCase):
    def test_true_when_marker_present(self):
        with tempfile.TemporaryDirectory() as d:
            wf_dir = Path(d)
            (wf_dir / "gated.yml").write_text("if: vars.AGENT_OPS_PAUSED != 'true'\n")
            self.assertTrue(hb.pause_gated(wf_dir, "gated.yml"))

    def test_false_when_marker_absent(self):
        with tempfile.TemporaryDirectory() as d:
            wf_dir = Path(d)
            (wf_dir / "ungated.yml").write_text("on: workflow_dispatch\n")
            self.assertFalse(hb.pause_gated(wf_dir, "ungated.yml"))

    def test_missing_file_defaults_to_false_and_warns(self):
        with tempfile.TemporaryDirectory() as d:
            wf_dir = Path(d)
            self.assertFalse(hb.pause_gated(wf_dir, "nope.yml"))


class TestEvaluate(unittest.TestCase):
    def _run(self, monitored, *, skip=frozenset(), paused=False, workflows_dir=None, fetch_map=None):
        fetch_map = fetch_map or {}
        calls = []

        def fetch_fn(wf):
            calls.append(wf)
            return fetch_map.get(wf, [])

        result = hb.evaluate(
            now=NOW, skip=set(skip), paused=paused,
            workflows_dir=workflows_dir or Path("/nonexistent"),
            fetch_fn=fetch_fn, monitored=monitored,
        )
        return result, calls

    def test_skipped_workflow_never_fetched(self):
        (problems, warnings, paused_skips, checked), calls = self._run(
            {"a.yml": 24, "b.yml": 24}, skip={"a.yml"}, fetch_map={"b.yml": [run_at(1)]},
        )
        self.assertEqual(calls, ["b.yml"])
        self.assertEqual(checked, 1)
        self.assertEqual(problems, [])

    def test_paused_and_gated_workflow_never_fetched(self):
        with tempfile.TemporaryDirectory() as d:
            wf_dir = Path(d)
            (wf_dir / "gated.yml").write_text("AGENT_OPS_PAUSED\n")
            (wf_dir / "ungated.yml").write_text("on: workflow_dispatch\n")
            (problems, warnings, paused_skips, checked), calls = self._run(
                {"gated.yml": 24, "ungated.yml": 24},
                paused=True, workflows_dir=wf_dir,
                fetch_map={"ungated.yml": [run_at(1)]},
            )
            self.assertEqual(calls, ["ungated.yml"])
            self.assertEqual(paused_skips, ["gated.yml"])
            self.assertEqual(checked, 1)

    def test_not_paused_gated_workflow_still_fetched(self):
        with tempfile.TemporaryDirectory() as d:
            wf_dir = Path(d)
            (wf_dir / "gated.yml").write_text("AGENT_OPS_PAUSED\n")
            (problems, warnings, paused_skips, checked), calls = self._run(
                {"gated.yml": 24}, paused=False, workflows_dir=wf_dir,
                fetch_map={"gated.yml": [run_at(1)]},
            )
            self.assertEqual(calls, ["gated.yml"])
            self.assertEqual(paused_skips, [])
            self.assertEqual(checked, 1)

    def test_problems_and_warnings_accumulate_across_workflows(self):
        (problems, warnings, paused_skips, checked), _ = self._run(
            {"a.yml": 24, "b.yml": 24},
            fetch_map={"a.yml": [run_at(48)], "b.yml": {"error": "timeout"}},
        )
        self.assertEqual(len(problems), 1)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(checked, 2)


class TestRender(unittest.TestCase):
    def test_healthy_report_is_just_the_header(self):
        text = hb.render("org/repo", [], [], set(), [])
        self.assertEqual(text, "*Pipeline heartbeat — org/repo*")

    def test_full_report_contains_all_sections(self):
        text = hb.render("org/repo", ["p1"], ["w1"], {"muted.yml"}, ["gated.yml"])
        self.assertIn("*Problems:*", text)
        self.assertIn("• p1", text)
        self.assertIn("*Warnings:*", text)
        self.assertIn("• w1", text)
        self.assertIn("Muted checks (HEARTBEAT_SKIP): muted.yml", text)
        self.assertIn("AGENT_OPS_PAUSED=true", text)
        self.assertIn("gated.yml", text)


if __name__ == "__main__":
    unittest.main()
