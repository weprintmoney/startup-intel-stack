"""Unit tests for lib/reply_monitor.py — Hard Rule 5 enforcement.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# crm.py imports requests (used as a type annotation, evaluated at import
# time) and imap_poll.py imports it too; lib-tests.yml doesn't install
# dependencies (same convention as test_send_queue.py).
if "requests" not in sys.modules:
    sys.modules["requests"] = types.ModuleType("requests")
_requests_mod = sys.modules["requests"]
if not hasattr(_requests_mod, "Response"):
    _requests_mod.Response = type("Response", (), {})


import reply_monitor as rm  # noqa: E402


def reply(**overrides):
    r = {"from": "Jane Doe <jane@example.com>", "subject": "Re: intro", "date": "2026-09-12", "body_snippet": "thanks"}
    r.update(overrides)
    return r


class IsUnsubscribe(unittest.TestCase):
    def test_keyword_in_subject_matches(self):
        self.assertTrue(rm.is_unsubscribe(reply(subject="please unsubscribe")))

    def test_keyword_in_body_matches(self):
        self.assertTrue(rm.is_unsubscribe(reply(body_snippet="take me off this list please")))

    def test_case_insensitive(self):
        self.assertTrue(rm.is_unsubscribe(reply(subject="UNSUBSCRIBE ME")))

    def test_no_keyword_does_not_match(self):
        self.assertFalse(rm.is_unsubscribe(reply(subject="Sounds good", body_snippet="let's talk")))


class ExtractEmail(unittest.TestCase):
    def test_angle_bracket_form(self):
        self.assertEqual(rm.extract_email("Jane Doe <jane@example.com>"), "jane@example.com")

    def test_bare_address_passes_through(self):
        self.assertEqual(rm.extract_email("jane@example.com"), "jane@example.com")


class HandleUnsubscribe(unittest.TestCase):
    def setUp(self):
        self._owner, self._escalation = rm.OWNER_UID, rm.ESCALATION_UID
        rm.OWNER_UID, rm.ESCALATION_UID = "U_OWNER", "U_ESCALATION"

    def tearDown(self):
        rm.OWNER_UID, rm.ESCALATION_UID = self._owner, self._escalation

    def test_suppresses_updates_crm_and_dms_owner_only(self):
        with patch("reply_monitor.suppression.add") as sup_add, \
             patch("reply_monitor.crm.set_field") as set_field, \
             patch("reply_monitor.crm.log_interaction") as log_interaction, \
             patch("reply_monitor.slack.post") as slack_post:
            rm.handle_unsubscribe("jane@example.com", "rec_1", "Jane <jane@example.com>", "2026-09-12")

        sup_add.assert_called_once_with("jane@example.com", "unsubscribed", "reply-monitor")
        set_field.assert_any_call("rec_1", "suppressed", True)
        set_field.assert_any_call("rec_1", "sequence_status", "paused")
        log_interaction.assert_called_once()
        slack_post.assert_called_once()
        self.assertEqual(slack_post.call_args[0][0], rm.OWNER_UID)
        self.assertNotIn(rm.ESCALATION_UID, [c.args[0] for c in slack_post.call_args_list])

    def test_no_record_id_skips_crm_but_still_suppresses_and_dms(self):
        with patch("reply_monitor.suppression.add") as sup_add, \
             patch("reply_monitor.crm.set_field") as set_field, \
             patch("reply_monitor.slack.post") as slack_post:
            rm.handle_unsubscribe("jane@example.com", None, "Jane <jane@example.com>", "2026-09-12")
        sup_add.assert_called_once()
        set_field.assert_not_called()
        slack_post.assert_called_once()

    def test_suppression_error_does_not_raise(self):
        with patch("reply_monitor.suppression.add", side_effect=RuntimeError("disk full")), \
             patch("reply_monitor.crm.set_field"), \
             patch("reply_monitor.crm.log_interaction"), \
             patch("reply_monitor.slack.post") as slack_post:
            rm.handle_unsubscribe("jane@example.com", "rec_1", "Jane <jane@example.com>", "2026-09-12")
        slack_post.assert_called_once()  # still notifies even if suppression itself errored

    def test_crm_error_does_not_raise_or_block_the_dm(self):
        with patch("reply_monitor.suppression.add"), \
             patch("reply_monitor.crm.set_field", side_effect=RuntimeError("crm down")), \
             patch("reply_monitor.slack.post") as slack_post:
            rm.handle_unsubscribe("jane@example.com", "rec_1", "Jane <jane@example.com>", "2026-09-12")
        slack_post.assert_called_once()


class HandleNormalReply(unittest.TestCase):
    def setUp(self):
        self._owner, self._escalation = rm.OWNER_UID, rm.ESCALATION_UID
        rm.OWNER_UID, rm.ESCALATION_UID = "U_OWNER", "U_ESCALATION"

    def tearDown(self):
        rm.OWNER_UID, rm.ESCALATION_UID = self._owner, self._escalation

    def test_pauses_sequence_and_notifies_owner_and_escalation(self):
        with patch("reply_monitor.crm.set_field") as set_field, \
             patch("reply_monitor.crm.log_interaction") as log_interaction, \
             patch("reply_monitor.slack.post") as slack_post:
            rm.handle_normal_reply(
                "jane@example.com", "rec_1", "Jane <jane@example.com>", "Re: intro", "2026-09-12", channel="",
            )

        set_field.assert_any_call("rec_1", "sequence_status", "paused")
        set_field.assert_any_call("rec_1", "reply_received", True)
        log_interaction.assert_called_once()
        dm_targets = [c.args[0] for c in slack_post.call_args_list]
        self.assertIn(rm.OWNER_UID, dm_targets)
        self.assertIn(rm.ESCALATION_UID, dm_targets)
        self.assertEqual(len(slack_post.call_args_list), 2)  # no channel post when channel==""

    def test_posts_to_team_channel_when_configured(self):
        with patch("reply_monitor.crm.set_field"), \
             patch("reply_monitor.crm.log_interaction"), \
             patch("reply_monitor.slack.post") as slack_post:
            rm.handle_normal_reply(
                "jane@example.com", "rec_1", "Jane <jane@example.com>", "Re: intro", "2026-09-12", channel="C999",
            )

        targets = [c.args[0] for c in slack_post.call_args_list]
        self.assertEqual(targets, [rm.OWNER_UID, rm.ESCALATION_UID, "C999"])

    def test_no_record_id_still_notifies(self):
        with patch("reply_monitor.crm.set_field") as set_field, \
             patch("reply_monitor.slack.post") as slack_post:
            rm.handle_normal_reply(
                "jane@example.com", None, "Jane <jane@example.com>", "Re: intro", "2026-09-12", channel="",
            )
        set_field.assert_not_called()
        self.assertEqual(len(slack_post.call_args_list), 2)


class ProcessReply(unittest.TestCase):
    def test_routes_unsubscribe_replies_to_handle_unsubscribe(self):
        r = reply(subject="please unsubscribe")
        with patch("reply_monitor.crm.get_contact", return_value={"id": "rec_1"}), \
             patch("reply_monitor.handle_unsubscribe") as h_unsub, \
             patch("reply_monitor.handle_normal_reply") as h_normal:
            rm.process_reply(r, channel="")
        h_unsub.assert_called_once()
        h_normal.assert_not_called()

    def test_routes_normal_replies_to_handle_normal_reply(self):
        r = reply()
        with patch("reply_monitor.crm.get_contact", return_value=None), \
             patch("reply_monitor.handle_unsubscribe") as h_unsub, \
             patch("reply_monitor.handle_normal_reply") as h_normal:
            rm.process_reply(r, channel="")
        h_normal.assert_called_once()
        h_unsub.assert_not_called()

    def test_looks_up_contact_by_extracted_email(self):
        r = reply(**{"from": "Jane Doe <jane@example.com>"})
        with patch("reply_monitor.crm.get_contact", return_value=None) as get_contact, \
             patch("reply_monitor.handle_normal_reply"):
            rm.process_reply(r, channel="")
        get_contact.assert_called_once_with("jane@example.com")


class Main(unittest.TestCase):
    def test_no_replies_is_a_clean_noop(self):
        with patch("reply_monitor.imap_poll.check_replies", return_value=[]), \
             patch("reply_monitor.process_reply") as process:
            rc = rm.main()
        self.assertEqual(rc, 0)
        process.assert_not_called()

    def test_each_reply_is_processed(self):
        with patch("reply_monitor.imap_poll.check_replies", return_value=[reply(), reply()]), \
             patch("reply_monitor.process_reply") as process:
            rm.main()
        self.assertEqual(process.call_count, 2)


if __name__ == "__main__":
    unittest.main()
