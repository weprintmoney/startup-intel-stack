"""Unit tests for lib/slack.py. No real network calls — urlopen is mocked.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from slack import post  # noqa: E402


def _ok_response(body):
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(body).encode()
    return cm


class Post(unittest.TestCase):
    def test_no_token_returns_false_without_network_call(self):
        with patch("slack.urllib.request.urlopen") as mock_open:
            ok = post("C123", "hello", token="")
            self.assertFalse(ok)
            mock_open.assert_not_called()

    def test_successful_post_returns_true(self):
        with patch("slack.urllib.request.urlopen", return_value=_ok_response({"ok": True})):
            ok = post("C123", "hello", token="xoxb-fake")
            self.assertTrue(ok)

    def test_api_rejection_returns_false(self):
        rejection = _ok_response({"ok": False, "error": "channel_not_found"})
        with patch("slack.urllib.request.urlopen", return_value=rejection):
            ok = post("C123", "hello", token="xoxb-fake")
            self.assertFalse(ok)

    def test_network_error_returns_false_not_raises(self):
        with patch("slack.urllib.request.urlopen", side_effect=urllib.error.URLError("boom")):
            ok = post("C123", "hello", token="xoxb-fake")
            self.assertFalse(ok)

    def test_request_payload_shape(self):
        with patch("slack.urllib.request.urlopen", return_value=_ok_response({"ok": True})) as mock_open:
            post("C999", "the message", token="xoxb-fake")
            req = mock_open.call_args[0][0]
            self.assertEqual(req.full_url, "https://slack.com/api/chat.postMessage")
            sent = json.loads(req.data)
            self.assertEqual(sent, {"channel": "C999", "text": "the message"})
            self.assertEqual(req.headers["Authorization"], "Bearer xoxb-fake")


class PostViaWebhookFallback(unittest.TestCase):
    """No bot token configured — falls back to the incoming-webhook path
    (this repo's default; see channels.slack_webhook_secret)."""

    def test_channel_id_posts_via_webhook_when_no_token(self):
        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.example/x"}, clear=False), \
             patch("slack.urllib.request.urlopen") as mock_open:
            ok = post("C123", "hello", token="")
        self.assertTrue(ok)
        req = mock_open.call_args[0][0]
        self.assertEqual(req.full_url, "https://hooks.slack.example/x")
        self.assertEqual(json.loads(req.data), {"text": "hello"})

    def test_user_id_is_not_sent_to_the_whole_channel(self):
        # A webhook can't DM — silently skip rather than blast a DM-only
        # alert to everyone in the webhook's channel.
        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.example/x"}, clear=False), \
             patch("slack.urllib.request.urlopen") as mock_open:
            ok = post("U097ZGYPX9Q", "hello", token="")
        self.assertFalse(ok)
        mock_open.assert_not_called()

    def test_webhook_network_error_returns_false_not_raises(self):
        with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.example/x"}, clear=False), \
             patch("slack.urllib.request.urlopen", side_effect=urllib.error.URLError("boom")):
            ok = post("C123", "hello", token="")
        self.assertFalse(ok)

    def test_neither_token_nor_webhook_returns_false(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("SLACK_BOT_TOKEN", None)
            os.environ.pop("SLACK_WEBHOOK_URL", None)
            with patch("slack.urllib.request.urlopen") as mock_open:
                ok = post("C123", "hello", token="")
        self.assertFalse(ok)
        mock_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
