"""Payload-shape tests for lib/smtp_send.py's three provider senders.

Narrow by design: covers the reply_to wiring (each provider has a different
field name/shape for it) without re-testing requests itself.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

if "requests" not in sys.modules:
    sys.modules["requests"] = types.ModuleType("requests")
if not hasattr(sys.modules["requests"], "post"):
    sys.modules["requests"].post = lambda *a, **k: None

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import smtp_send  # noqa: E402

BASE_PAYLOAD = {"to": "lead@example.com", "subject": "Hi", "text": "body", "html": None, "bcc": None}


def _ok_response():
    r = MagicMock()
    r.status_code = 200
    return r


class SendResendReplyTo(unittest.TestCase):
    def test_reply_to_included_when_set(self):
        with patch.dict("os.environ", {"RESEND_API_KEY": "k"}, clear=False), \
             patch("smtp_send.requests.post", return_value=_ok_response()) as mock_post:
            smtp_send._send_resend(
                {**BASE_PAYLOAD, "reply_to": "founder@example.com"}, "outreach@mail.example.com", "Jamie",
            )
        body = mock_post.call_args.kwargs["json"]
        self.assertEqual(body["reply_to"], "founder@example.com")

    def test_reply_to_omitted_when_absent(self):
        with patch.dict("os.environ", {"RESEND_API_KEY": "k"}, clear=False), \
             patch("smtp_send.requests.post", return_value=_ok_response()) as mock_post:
            smtp_send._send_resend({**BASE_PAYLOAD, "reply_to": None}, "outreach@mail.example.com", "Jamie")
        body = mock_post.call_args.kwargs["json"]
        self.assertNotIn("reply_to", body)


class SendSendgridReplyTo(unittest.TestCase):
    def test_reply_to_shape(self):
        with patch.dict("os.environ", {"SENDGRID_API_KEY": "k"}, clear=False), \
             patch("smtp_send.requests.post", return_value=_ok_response()) as mock_post:
            smtp_send._send_sendgrid(
                {**BASE_PAYLOAD, "reply_to": "founder@example.com"}, "outreach@mail.example.com", "Jamie",
            )
        body = mock_post.call_args.kwargs["json"]
        self.assertEqual(body["reply_to"], {"email": "founder@example.com"})


class SendMailgunReplyTo(unittest.TestCase):
    def test_reply_to_header_field(self):
        with patch.dict("os.environ", {"MAILGUN_API_KEY": "k"}, clear=False), \
             patch("smtp_send.requests.post", return_value=_ok_response()) as mock_post:
            smtp_send._send_mailgun(
                {**BASE_PAYLOAD, "reply_to": "founder@example.com"},
                "outreach@mail.example.com", "Jamie", "mail.example.com",
            )
        data = mock_post.call_args.kwargs["data"]
        self.assertEqual(data["h:Reply-To"], "founder@example.com")


class SendEmailIgnoreBusinessHours(unittest.TestCase):
    """format-test-send.yml sends outside business hours on purpose; every
    other caller must still respect the gate."""

    def setUp(self):
        self.env = patch.dict("os.environ", {"RESEND_API_KEY": "k"}, clear=False)
        self.env.start()
        self.profile = {
            "company": {"domain": "acme.example", "send_domain": "mail.acme.example", "hq_timezone": "UTC"},
            "sending": {"provider": "resend", "daily_cap": 100},
        }
        # Never touch the real sends/daily-count.json.
        self._real_path = smtp_send.DAILY_COUNT_PATH
        self.tmp_dir = tempfile.mkdtemp()
        smtp_send.DAILY_COUNT_PATH = Path(self.tmp_dir) / "daily-count.json"

    def tearDown(self):
        self.env.stop()
        smtp_send.DAILY_COUNT_PATH = self._real_path

    def test_outside_hours_blocked_by_default(self):
        with patch("smtp_send.config.load", return_value=self.profile), \
             patch("smtp_send._is_business_hours", return_value=False), \
             patch("smtp_send.requests.post") as mock_post:
            result = smtp_send.send_email(to="lead@example.com", subject="Hi", body="body")
        self.assertFalse(result["success"])
        self.assertIn("business hours", result["error"])
        mock_post.assert_not_called()

    def test_outside_hours_sends_when_ignored(self):
        with patch("smtp_send.config.load", return_value=self.profile), \
             patch("smtp_send._is_business_hours", return_value=False), \
             patch("smtp_send.requests.post", return_value=_ok_response()) as mock_post:
            result = smtp_send.send_email(to="lead@example.com", subject="Hi", body="body", ignore_business_hours=True)
        self.assertTrue(result["success"])
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
