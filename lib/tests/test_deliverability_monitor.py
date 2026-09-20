"""Unit tests for lib/deliverability_monitor.py.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import deliverability_monitor as dm  # noqa: E402


def _mxtoolbox_response(body: dict):
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = __import__("json").dumps(body).encode()
    return cm


class CheckBlacklist(unittest.TestCase):
    def test_clean_domain_returns_true_no_alert(self):
        with patch("deliverability_monitor.urllib.request.urlopen", return_value=_mxtoolbox_response({"Failed": []})), \
             patch("deliverability_monitor.slack_post") as slack_post:
            ok = dm.check_blacklist("mail.example.com")
        self.assertTrue(ok)
        slack_post.assert_not_called()

    def test_blacklisted_domain_returns_false_and_alerts_leadership(self):
        body = {"Failed": [{"Name": "Spamhaus"}, {"Name": "Barracuda"}]}
        with patch("deliverability_monitor.urllib.request.urlopen", return_value=_mxtoolbox_response(body)), \
             patch("deliverability_monitor.slack_post") as slack_post:
            ok = dm.check_blacklist("mail.example.com")
        self.assertFalse(ok)
        slack_post.assert_called_once()
        self.assertEqual(slack_post.call_args[0][0], dm.ALERT_CHANNEL)
        self.assertIn("Spamhaus", slack_post.call_args[0][1])
        self.assertIn("Barracuda", slack_post.call_args[0][1])

    def test_api_error_treated_as_ok_not_fatal(self):
        with patch("deliverability_monitor.urllib.request.urlopen", side_effect=RuntimeError("no api key")), \
             patch("deliverability_monitor.slack_post") as slack_post:
            ok = dm.check_blacklist("mail.example.com")
        self.assertTrue(ok)
        slack_post.assert_not_called()


class CheckPostmasterComplaintRate(unittest.TestCase):
    def test_no_credentials_returns_zero(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("GOOGLE_CREDENTIALS_JSON", None)
            rate = dm.check_postmaster_complaint_rate()
        self.assertEqual(rate, 0.0)

    def test_credentials_present_still_returns_zero_stub(self):
        # The real Postmaster Tools call was never wired up (ADC/JWT auth
        # missing) — this documents the stub behavior, not a real check.
        with patch.dict("os.environ", {"GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}'}):
            rate = dm.check_postmaster_complaint_rate()
        self.assertEqual(rate, 0.0)

    def test_malformed_credentials_do_not_raise(self):
        with patch.dict("os.environ", {"GOOGLE_CREDENTIALS_JSON": "not json"}):
            rate = dm.check_postmaster_complaint_rate()
        self.assertEqual(rate, 0.0)


class EvaluateAndAct(unittest.TestCase):
    def setUp(self):
        self._alert_uid = dm.ALERT_UID
        dm.ALERT_UID = "U_ALERT"

    def tearDown(self):
        dm.ALERT_UID = self._alert_uid

    def test_healthy_rate_is_a_noop(self):
        with patch("deliverability_monitor.set_repo_variable") as set_var, \
             patch("deliverability_monitor.slack_post") as slack_post:
            rc = dm.evaluate_and_act(0.0001, dns_ok=True)
        self.assertEqual(rc, 0)
        set_var.assert_not_called()
        slack_post.assert_not_called()

    def test_warning_threshold_pauses_and_alerts_channel_only(self):
        with patch("deliverability_monitor.set_repo_variable") as set_var, \
             patch("deliverability_monitor.slack_post") as slack_post:
            rc = dm.evaluate_and_act(0.002, dns_ok=True)  # >0.1%, <=0.3%
        self.assertEqual(rc, 0)
        set_var.assert_called_once_with("SEQUENCES_PAUSED", "true")
        slack_post.assert_called_once()
        self.assertEqual(slack_post.call_args[0][0], dm.ALERT_CHANNEL)

    def test_critical_threshold_hard_stops_alerts_both_and_exits_1(self):
        with patch("deliverability_monitor.set_repo_variable") as set_var, \
             patch("deliverability_monitor.slack_post") as slack_post:
            rc = dm.evaluate_and_act(0.005, dns_ok=True)  # >0.3%
        self.assertEqual(rc, 1)
        set_var.assert_called_once_with("SEQUENCES_PAUSED", "true")
        targets = [c.args[0] for c in slack_post.call_args_list]
        self.assertEqual(targets, [dm.ALERT_CHANNEL, dm.ALERT_UID])

    def test_threshold_boundaries_are_strictly_greater_than(self):
        with patch("deliverability_monitor.set_repo_variable") as set_var, \
             patch("deliverability_monitor.slack_post"):
            rc = dm.evaluate_and_act(0.001, dns_ok=True)  # exactly at the warning boundary
        self.assertEqual(rc, 0)
        set_var.assert_not_called()  # 0.001 is not > 0.001


class SetRepoVariable(unittest.TestCase):
    def test_no_token_or_repo_skips_the_call(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("GH_TOKEN", None)
            os.environ.pop("REPO", None)
            with patch("deliverability_monitor.urllib.request.urlopen") as m:
                dm.set_repo_variable("SEQUENCES_PAUSED", "true")
        m.assert_not_called()

    def test_request_shape_when_configured(self):
        with patch.dict("os.environ", {"GH_TOKEN": "ghp_fake", "REPO": "acme/startup-intel-stack"}), \
             patch("deliverability_monitor.urllib.request.urlopen") as m:
            dm.set_repo_variable("SEQUENCES_PAUSED", "true")
        m.assert_called_once()
        req = m.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.github.com/repos/acme/startup-intel-stack/actions/variables/SEQUENCES_PAUSED")
        self.assertEqual(req.get_method(), "PATCH")


class Main(unittest.TestCase):
    def test_wires_blacklist_and_complaint_rate_into_evaluate(self):
        with patch("deliverability_monitor.check_blacklist", return_value=True) as cb, \
             patch("deliverability_monitor.check_postmaster_complaint_rate", return_value=0.0) as cp, \
             patch("deliverability_monitor.evaluate_and_act", return_value=0) as ev:
            rc = dm.main()
        self.assertEqual(rc, 0)
        cb.assert_called_once()
        cp.assert_called_once()
        ev.assert_called_once_with(0.0, True)


if __name__ == "__main__":
    unittest.main()
