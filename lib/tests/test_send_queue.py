"""Unit tests for lib/send_queue.py — the highest-stakes extraction (real
prospect email). Every external call (smtp_send, suppression, crm, slack)
is mocked; nothing here sends a real email or hits a real API.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# send_queue imports crm and smtp_send, both of which import requests at
# module scope; these tests never reach the real API (same convention as
# test_smtp_send_ramp.py — lib-tests.yml doesn't install requests). crm.py
# additionally uses requests.Response as a type annotation evaluated at
# import time (no `from __future__ import annotations` there), so the stub
# needs an attribute for it — a plain bare module isn't enough.
if "requests" not in sys.modules:
    sys.modules["requests"] = types.ModuleType("requests")
_requests_mod = sys.modules["requests"]
if not hasattr(_requests_mod, "Response"):
    _requests_mod.Response = type("Response", (), {})


import send_queue as sq  # noqa: E402
import smtp_send  # noqa: E402

TODAY = "2026-09-12"


def write_item(path: Path, item: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(item))


def good_item(**overrides):
    item = {"to": "lead@example.com", "subject": "Hi", "body": "Body text"}
    item.update(overrides)
    return item


class ProcessItemSkips(unittest.TestCase):
    """Paths that never reach smtp_send.send_email and return None."""

    def test_malformed_item_missing_field_skips(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            write_item(p, {"to": "a@example.com", "subject": "Hi"})  # no body
            with patch("send_queue.smtp_send.send_email") as m:
                result = sq.process_item(p, {"to": "a@example.com", "subject": "Hi"}, today=TODAY)
            self.assertIsNone(result)
            m.assert_not_called()
            self.assertTrue(p.exists())  # not unlinked

    def test_linkedin_channel_skips(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item(channel="linkedin")
            write_item(p, item)
            with patch("send_queue.smtp_send.send_email") as m:
                result = sq.process_item(p, item, today=TODAY)
            self.assertIsNone(result)
            m.assert_not_called()
            self.assertTrue(p.exists())

    def test_not_due_yet_skips_without_unlink(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item(scheduled_date="2026-09-20")
            write_item(p, item)
            with patch("send_queue.smtp_send.send_email") as m:
                result = sq.process_item(p, item, today=TODAY)
            self.assertIsNone(result)
            m.assert_not_called()
            self.assertTrue(p.exists())

    def test_suppressed_skips_and_unlinks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item()
            write_item(p, item)
            with patch("send_queue.suppression.check", return_value=True), \
                 patch("send_queue.smtp_send.send_email") as m:
                result = sq.process_item(p, item, today=TODAY)
            self.assertIsNone(result)
            m.assert_not_called()
            self.assertFalse(p.exists())

    def test_crm_lookup_failure_skips_without_unlink(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item()
            write_item(p, item)
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", side_effect=RuntimeError("timeout")), \
                 patch("send_queue.smtp_send.send_email") as m:
                result = sq.process_item(p, item, today=TODAY)
            self.assertIsNone(result)
            m.assert_not_called()
            self.assertTrue(p.exists())

    def test_paused_sequence_skips_and_unlinks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item()
            write_item(p, item)
            contact = {"sequence_status": "paused"}  # crm.get_contact() returns a normalized flat dict
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=contact), \
                 patch("send_queue.smtp_send.send_email") as m:
                result = sq.process_item(p, item, today=TODAY)
            self.assertIsNone(result)
            m.assert_not_called()
            self.assertFalse(p.exists())

    def test_no_contact_found_proceeds_to_send(self):
        # get_contact returning None (no CRM record) must NOT be treated
        # as paused/rejected/completed — the original checked seq_status
        # only `if contact:`.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item()
            write_item(p, item)
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email",
                       return_value={"success": True, "error": None, "smtp_code": 200, "hard_bounce": False}):
                result = sq.process_item(p, item, today=TODAY)
            self.assertIsNotNone(result)
            self.assertTrue(result["success"])


class ProcessItemSendOutcomes(unittest.TestCase):
    def _base_patches(self, contact=None):
        return [
            patch("send_queue.suppression.check", return_value=False),
            patch("send_queue.crm.get_contact", return_value=contact),
        ]

    def test_daily_cap_propagates_uncaught(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item()
            write_item(p, item)
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email", side_effect=smtp_send.DailyCap("cap hit")):
                with self.assertRaises(smtp_send.DailyCap):
                    sq.process_item(p, item, today=TODAY)
            self.assertTrue(p.exists())  # never unlinked — still queued for tomorrow

    def test_success_updates_crm_and_unlinks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item(contact_id="rec_1", touch_number=1, from_name="Nic")
            write_item(p, item)
            send_result = {"success": True, "error": None, "smtp_code": 200, "hard_bounce": False}
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email", return_value=send_result), \
                 patch("send_queue.crm.set_field") as set_field, \
                 patch("send_queue.crm.log_interaction") as log_interaction:
                result = sq.process_item(p, item, today=TODAY)
            self.assertTrue(result["success"])
            self.assertEqual(result["to"], "lead@example.com")
            self.assertEqual(result["item"], "item.json")
            self.assertFalse(p.exists())
            # touch_number 1 sets sequence_status + enrolled_date in addition
            # to last_touch_date/number
            set_field.assert_any_call("rec_1", "last_touch_date", TODAY)
            set_field.assert_any_call("rec_1", "last_touch_number", 1)
            set_field.assert_any_call("rec_1", "sequence_status", "enrolled")
            set_field.assert_any_call("rec_1", "sequence_enrolled_date", TODAY)
            log_interaction.assert_called_once()

    def test_success_touch_2_does_not_set_enrolled_fields(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item(contact_id="rec_1", touch_number=2)
            write_item(p, item)
            send_result = {"success": True, "error": None, "smtp_code": 200, "hard_bounce": False}
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email", return_value=send_result), \
                 patch("send_queue.crm.set_field") as set_field, \
                 patch("send_queue.crm.log_interaction"):
                sq.process_item(p, item, today=TODAY)
            calls = [c.args[1] for c in set_field.call_args_list]
            self.assertNotIn("sequence_status", calls)
            self.assertNotIn("sequence_enrolled_date", calls)

    def test_success_with_no_contact_id_skips_crm_update_but_still_sends(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item()  # no contact_id
            write_item(p, item)
            send_result = {"success": True, "error": None, "smtp_code": 200, "hard_bounce": False}
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email", return_value=send_result), \
                 patch("send_queue.crm.set_field") as set_field:
                result = sq.process_item(p, item, today=TODAY)
            self.assertTrue(result["success"])
            set_field.assert_not_called()
            self.assertFalse(p.exists())

    def test_crm_update_failure_does_not_raise_and_still_unlinks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item(contact_id="rec_1")
            write_item(p, item)
            send_result = {"success": True, "error": None, "smtp_code": 200, "hard_bounce": False}
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email", return_value=send_result), \
                 patch("send_queue.crm.set_field", side_effect=RuntimeError("crm down")):
                result = sq.process_item(p, item, today=TODAY)
            self.assertTrue(result["success"])
            self.assertFalse(p.exists())

    def test_hard_bounce_suppresses_and_unlinks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item()
            write_item(p, item)
            send_result = {"success": False, "error": "invalid address", "smtp_code": 422, "hard_bounce": True}
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email", return_value=send_result), \
                 patch("send_queue.suppression.add") as sup_add:
                result = sq.process_item(p, item, today=TODAY)
            self.assertFalse(result["success"])
            sup_add.assert_called_once_with("lead@example.com", "bounced_hard", "smtp-send-workflow")
            self.assertFalse(p.exists())

    def test_soft_bounce_alerts_slack_and_keeps_item_queued(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item()
            write_item(p, item)
            send_result = {"success": False, "error": "temporary failure", "smtp_code": 500, "hard_bounce": False}
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email", return_value=send_result), \
                 patch.dict("os.environ", {"SLACK_SALES_REVIEW_CHANNEL": "C123"}), \
                 patch("send_queue.slack.post") as slack_post:
                result = sq.process_item(p, item, today=TODAY)
            self.assertFalse(result["success"])
            self.assertTrue(p.exists())  # left queued — a real send may succeed later
            slack_post.assert_called_once()
            self.assertEqual(slack_post.call_args[0][0], "C123")
            self.assertIn("lead@example.com", slack_post.call_args[0][1])

    def test_soft_bounce_with_no_channel_configured_does_not_call_slack(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "item.json"
            item = good_item()
            write_item(p, item)
            send_result = {"success": False, "error": "temporary failure", "smtp_code": 500, "hard_bounce": False}
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email", return_value=send_result), \
                 patch.dict("os.environ", {}, clear=False), \
                 patch("send_queue.slack.post") as slack_post:
                import os
                os.environ.pop("SLACK_SALES_REVIEW_CHANNEL", None)
                sq.process_item(p, item, today=TODAY)
            slack_post.assert_not_called()


class ProcessQueue(unittest.TestCase):
    def test_empty_queue_writes_no_log_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            results = sq.process_queue(root / "queue", root / "log", today=TODAY)
            self.assertEqual(results, [])
            self.assertFalse((root / "log" / f"{TODAY}-sends.jsonl").exists())

    def test_sleep_only_after_a_real_send_attempt_not_on_early_skips(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            queue_dir = root / "queue"
            # One item skipped early (malformed — no body), one that sends.
            write_item(queue_dir / "a-malformed.json", {"to": "x@example.com", "subject": "Hi"})
            write_item(queue_dir / "b-good.json", good_item(to="y@example.com"))

            sleeps = []
            send_result = {"success": True, "error": None, "smtp_code": 200, "hard_bounce": False}
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email", return_value=send_result):
                sq.process_queue(queue_dir, root / "log", today=TODAY, sleep_fn=sleeps.append)

            self.assertEqual(len(sleeps), 1)  # only the one real send slept

    def test_daily_cap_stops_batch_and_logs_only_prior_sends(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            queue_dir = root / "queue"
            write_item(queue_dir / "a-first.json", good_item(to="first@example.com"))
            write_item(queue_dir / "b-second.json", good_item(to="second@example.com"))

            send_result = {"success": True, "error": None, "smtp_code": 200, "hard_bounce": False}
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email",
                       side_effect=[send_result, smtp_send.DailyCap("cap hit")]):
                results = sq.process_queue(queue_dir, root / "log", today=TODAY, sleep_fn=lambda _: None)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["to"], "first@example.com")
            log_path = root / "log" / f"{TODAY}-sends.jsonl"
            lines = log_path.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["to"], "first@example.com")
            # second item still queued (DailyCap hit before it could send)
            self.assertTrue((queue_dir / "b-second.json").exists())

    def test_log_line_shape_matches_result_dict(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            queue_dir = root / "queue"
            write_item(queue_dir / "a.json", good_item())
            send_result = {"success": True, "error": None, "smtp_code": 200, "hard_bounce": False}
            with patch("send_queue.suppression.check", return_value=False), \
                 patch("send_queue.crm.get_contact", return_value=None), \
                 patch("send_queue.smtp_send.send_email", return_value=send_result):
                sq.process_queue(queue_dir, root / "log", today=TODAY, sleep_fn=lambda _: None)
            line = json.loads((root / "log" / f"{TODAY}-sends.jsonl").read_text().splitlines()[0])
            self.assertEqual(
                set(line.keys()),
                {"success", "error", "smtp_code", "hard_bounce", "to", "item"},
            )


if __name__ == "__main__":
    unittest.main()
