"""Warmup-ramp behaviour for lib/smtp_send.py.

This logic decides whether prospect email actually leaves the building, and
its failure modes are quiet ones — a ramp that resets nightly pins the domain
at its lowest step forever; an internal exemption that leaks lets test sends
eat the prospect budget. Both are covered here.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

# smtp_send imports requests at module scope; these tests never reach the API.
# Idempotent: adds only what's missing, so it doesn't matter whether another
# test file's (possibly richer) stub already occupies sys.modules["requests"].
if "requests" not in sys.modules:
    sys.modules["requests"] = types.ModuleType("requests")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import smtp_send  # noqa: E402

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


class RampTestCase(unittest.TestCase):
    def setUp(self):
        self._real_path = smtp_send.DAILY_COUNT_PATH
        self.tmp = Path(tempfile.mkdtemp()) / "daily-count.json"
        smtp_send.DAILY_COUNT_PATH = self.tmp

    def tearDown(self):
        smtp_send.DAILY_COUNT_PATH = self._real_path

    def write(self, record):
        self.tmp.write_text(json.dumps(record))

    def read(self):
        return json.loads(self.tmp.read_text())


class TestRampCurve(unittest.TestCase):
    def test_steps_at_ramp_width_boundaries(self):
        # daily_cap=100, ramp_days=25 -> width=5, steps at 5/10/15/20/25
        for send_days, expected in [
            (0, 5), (1, 5), (5, 5),
            (6, 10), (10, 10),
            (11, 20), (15, 20),
            (16, 40), (20, 40),
            (21, 75), (25, 75),
            (26, 100), (999, 100),
        ]:
            with self.subTest(send_days=send_days):
                self.assertEqual(smtp_send.current_daily_cap(100, 25, send_days), expected)

    def test_scales_with_daily_cap(self):
        # Proportions hold regardless of the steady-state cap.
        self.assertEqual(smtp_send.current_daily_cap(40, 25, 1), 2)  # round(40*0.05)
        self.assertEqual(smtp_send.current_daily_cap(40, 25, 26), 40)

    def test_ramp_disabled_applies_full_cap_immediately(self):
        self.assertEqual(smtp_send.current_daily_cap(100, 0, 0), 100)
        self.assertEqual(smtp_send.current_daily_cap(100, 0, 1), 100)


class TestCheckAndIncrement(RampTestCase):
    def test_new_day_uses_ramped_cap_and_advances_send_days(self):
        self.write({"date": "2020-01-01", "count": 0, "send_days": 0})
        smtp_send._check_and_increment_daily_count(daily_cap=100, ramp_days=25)
        record = self.read()
        self.assertEqual(record["send_days"], 1)
        self.assertEqual(record["date"], TODAY)
        self.assertEqual(record["count"], 1)

    def test_same_day_does_not_advance_send_days(self):
        self.write({"date": TODAY, "count": 2, "send_days": 3})
        smtp_send._check_and_increment_daily_count(daily_cap=100, ramp_days=25)
        record = self.read()
        self.assertEqual(record["send_days"], 3)
        self.assertEqual(record["count"], 3)

    def test_pause_does_not_advance_ramp_across_the_gap(self):
        # 10 sending-days in, then a multi-week pause with zero sends. The
        # ramp must resume exactly where it left off, not jump ahead because
        # calendar time passed.
        self.write({"date": "2020-01-01", "count": 10, "send_days": 10})
        smtp_send._check_and_increment_daily_count(daily_cap=100, ramp_days=25)
        record = self.read()
        self.assertEqual(record["send_days"], 11)  # one sending-day, not one calendar-gap

    def test_cap_reached_raises(self):
        self.write({"date": TODAY, "count": 5, "send_days": 1})
        with self.assertRaises(smtp_send.DailyCap):
            smtp_send._check_and_increment_daily_count(daily_cap=100, ramp_days=25)

    def test_internal_send_does_not_advance_send_days(self):
        # Internal (own-domain) sends are seed traffic for reputation, not
        # cold reach — they must not consume ramp budget.
        self.write({"date": "2020-01-01", "count": 0, "send_days": 5})
        smtp_send._check_and_increment_daily_count(daily_cap=100, ramp_days=25, internal=True)
        record = self.read()
        self.assertEqual(record["send_days"], 5)
        self.assertEqual(record["count"], 1)

    def test_missing_file_starts_at_zero(self):
        smtp_send._check_and_increment_daily_count(daily_cap=100, ramp_days=25)
        record = self.read()
        self.assertEqual(record["send_days"], 1)
        self.assertEqual(record["count"], 1)


if __name__ == "__main__":
    unittest.main()
