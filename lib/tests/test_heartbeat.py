"""Unit tests for lib/heartbeat.py.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import heartbeat as hb  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

NOW = datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc)


def run(created_at: str, conclusion: str = "success", url: str = "https://x/run/1"):
    return {"conclusion": conclusion, "created_at": created_at, "html_url": url}


class MonitoredKeysAreRealFiles(unittest.TestCase):
    def test_every_monitored_key_is_a_real_workflow_file(self):
        # This is the one invariant the plan calls out explicitly: no dead
        # entries pointing at a workflow that no longer exists (or was
        # renamed) — that would silently stop alerting on it.
        missing = [wf for wf in hb.MONITORED if not (WORKFLOWS_DIR / wf).exists()]
        self.assertEqual(missing, [], f"MONITORED names workflow file(s) that don't exist: {missing}")


class MonitoredForStage(unittest.TestCase):
    def test_pre_seed_and_seed_only_monitor_the_always_on_workflows(self):
        for stage in ("pre-seed", "seed", "unknown-future-stage"):
            with self.subTest(stage=stage):
                monitored = hb._monitored_for_stage(stage)
                self.assertEqual(set(monitored), {"weekly-crawl.yml", "dedup-review.yml"})

    def test_series_a_adds_the_send_loop_workflows(self):
        monitored = hb._monitored_for_stage("series-a")
        self.assertEqual(
            set(monitored),
            {
                "weekly-crawl.yml", "dedup-review.yml", "deliverability-monitor.yml",
                "smtp-send.yml", "reply-monitor.yml",
            },
        )

    def test_windows_come_from_the_module_level_monitored_dict(self):
        monitored = hb._monitored_for_stage("series-a")
        self.assertEqual(monitored["smtp-send.yml"], hb.MONITORED["smtp-send.yml"])


class Evaluate(unittest.TestCase):
    def test_healthy_is_no_problems_no_warnings(self):
        runs_by_workflow = {wf: [run(NOW.isoformat().replace("+00:00", "Z"))] for wf in hb.MONITORED}
        problems, warnings = hb.evaluate(
            now=NOW, skip=set(), in_business_window=False,
            runs_by_workflow=runs_by_workflow, daily_count=None, raw_lead_dates=[],
        )
        self.assertEqual(problems, [])
        self.assertEqual(warnings, [])

    def test_stale_workflow_is_a_problem(self):
        stale = (NOW - timedelta(hours=300)).isoformat().replace("+00:00", "Z")
        runs_by_workflow = {"weekly-crawl.yml": [run(stale)]}
        problems, _ = hb.evaluate(
            now=NOW, skip=set(), in_business_window=False,
            runs_by_workflow=runs_by_workflow, daily_count=None, raw_lead_dates=[],
            monitored={"weekly-crawl.yml": 204},
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("300h ago", problems[0])

    def test_latest_run_failed_is_a_problem(self):
        runs_by_workflow = {"smtp-send.yml": [
            run(NOW.isoformat().replace("+00:00", "Z"), conclusion="failure"),
            run(NOW.isoformat().replace("+00:00", "Z"), conclusion="success"),
        ]}
        problems, _ = hb.evaluate(
            now=NOW, skip=set(), in_business_window=False,
            runs_by_workflow=runs_by_workflow, daily_count=None, raw_lead_dates=[],
            monitored={"smtp-send.yml": 28},
        )
        self.assertTrue(any("concluded *failure*" in p for p in problems))

    def test_no_completed_runs_at_all_is_a_problem(self):
        problems, _ = hb.evaluate(
            now=NOW, skip=set(), in_business_window=False,
            runs_by_workflow={"smtp-send.yml": []}, daily_count=None, raw_lead_dates=[],
            monitored={"smtp-send.yml": 28},
        )
        self.assertTrue(any("no completed runs found at all" in p for p in problems))

    def test_no_successful_run_among_completed_is_a_problem(self):
        runs_by_workflow = {"smtp-send.yml": [run(NOW.isoformat().replace("+00:00", "Z"), conclusion="failure")]}
        problems, _ = hb.evaluate(
            now=NOW, skip=set(), in_business_window=False,
            runs_by_workflow=runs_by_workflow, daily_count=None, raw_lead_dates=[],
            monitored={"smtp-send.yml": 28},
        )
        self.assertTrue(any("no successful run in the last" in p for p in problems))

    def test_api_error_is_a_warning_not_a_problem(self):
        problems, warnings = hb.evaluate(
            now=NOW, skip=set(), in_business_window=False,
            runs_by_workflow={"smtp-send.yml": {"error": "timeout"}}, daily_count=None, raw_lead_dates=[],
            monitored={"smtp-send.yml": 28},
        )
        self.assertEqual(problems, [])
        self.assertTrue(any("could not read run history" in w for w in warnings))

    def test_skip_excludes_a_workflow_entirely(self):
        problems, warnings = hb.evaluate(
            now=NOW, skip={"smtp-send.yml"}, in_business_window=False,
            runs_by_workflow={}, daily_count=None, raw_lead_dates=[],
            monitored={"smtp-send.yml": 28},
        )
        self.assertEqual(problems, [])
        self.assertEqual(warnings, [])

    def test_critical_reply_monitor_stale_after_recent_send(self):
        stale_reply = (NOW - timedelta(hours=10)).isoformat().replace("+00:00", "Z")
        runs_by_workflow = {"reply-monitor.yml": [run(stale_reply)]}
        problems, _ = hb.evaluate(
            now=NOW, skip=set(), in_business_window=True,
            runs_by_workflow=runs_by_workflow,
            daily_count={"count": 5, "date": NOW.date().isoformat()},
            raw_lead_dates=[],
            monitored={"reply-monitor.yml": 28},
        )
        self.assertTrue(problems[0].startswith(":rotating_light: *CRITICAL*"))

    def test_critical_does_not_fire_outside_business_window(self):
        stale_reply = (NOW - timedelta(hours=10)).isoformat().replace("+00:00", "Z")
        runs_by_workflow = {"reply-monitor.yml": [run(stale_reply)]}
        problems, _ = hb.evaluate(
            now=NOW, skip=set(), in_business_window=False,
            runs_by_workflow=runs_by_workflow,
            daily_count={"count": 5, "date": NOW.date().isoformat()},
            raw_lead_dates=[],
            monitored={"reply-monitor.yml": 999},  # not stale by its own window either
        )
        self.assertEqual(problems, [])

    def test_zero_output_warning_when_crawl_green_but_no_fresh_raw_file(self):
        runs_by_workflow = {"weekly-crawl.yml": [run(NOW.isoformat().replace("+00:00", "Z"))]}
        old_date = (NOW - timedelta(days=15)).date().isoformat()
        _, warnings = hb.evaluate(
            now=NOW, skip=set(), in_business_window=False,
            runs_by_workflow=runs_by_workflow, daily_count=None,
            raw_lead_dates=[old_date],
            monitored={"weekly-crawl.yml": 204},
        )
        self.assertTrue(any("newest `leads/raw/`" in w for w in warnings))

    def test_zero_output_not_duplicated_when_already_a_problem(self):
        # weekly-crawl itself stale -> already a problem; zero-output warning
        # must not also fire for the same workflow.
        stale = (NOW - timedelta(hours=300)).isoformat().replace("+00:00", "Z")
        runs_by_workflow = {"weekly-crawl.yml": [run(stale)]}
        old_date = (NOW - timedelta(days=15)).date().isoformat()
        problems, warnings = hb.evaluate(
            now=NOW, skip=set(), in_business_window=False,
            runs_by_workflow=runs_by_workflow, daily_count=None,
            raw_lead_dates=[old_date],
            monitored={"weekly-crawl.yml": 204},
        )
        self.assertEqual(len(problems), 1)
        self.assertEqual(warnings, [])


class Render(unittest.TestCase):
    def test_shape_includes_all_sections(self):
        text = hb.render("acme/startup-intel-stack", ["p1"], ["w1"], {"smtp-send.yml"})
        self.assertIn("*Pipeline heartbeat — acme/startup-intel-stack*", text)
        self.assertIn("*Problems:*", text)
        self.assertIn("• p1", text)
        self.assertIn("*Warnings:*", text)
        self.assertIn("• w1", text)
        self.assertIn("Muted checks (HEARTBEAT_SKIP): smtp-send.yml", text)

    def test_no_optional_sections_when_empty(self):
        text = hb.render("acme/startup-intel-stack", [], [], set())
        self.assertNotIn("*Problems:*", text)
        self.assertNotIn("*Warnings:*", text)
        self.assertNotIn("Muted checks", text)


if __name__ == "__main__":
    unittest.main()
