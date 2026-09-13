"""Single Slack sender for the outbound pipeline.

Two ways to notify, tried in this order:

1. **Bot token** (`SLACK_BOT_TOKEN`) — posts via `chat.postMessage` to any
   channel ID *or* DMs a specific user ID. Needed for the "alert one person
   directly" pattern (an owner/escalation UID on a hard-stop). Requires a
   Slack App with a bot token installed to the workspace.
2. **Incoming webhook** (`SLACK_WEBHOOK_URL`, mapped from
   `channels.slack_webhook_secret` in company-profile.yaml — this repo's
   default notification path, used by every other workflow) — posts to the
   one channel the webhook is bound to. No DM support, so a `channel`
   argument that looks like a user ID (starts with "U") is silently skipped
   rather than misdelivered to the whole channel.

If neither is configured, `post()` prints and returns False — never raises.
A Slack outage should never fail the job whose real work already succeeded
or failed on its own terms.

CLI: python3 lib/slack.py <channel> <text>
"""

import json
import os
import sys
import urllib.error
import urllib.request


def _post_via_bot(channel: str, text: str, token: str) -> bool:
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps({"channel": channel, "text": text}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"slack: post to {channel} failed: {e}")
        return False
    if not body.get("ok"):
        print(f"slack: post to {channel} rejected by API: {body.get('error')}")
        return False
    return True


def _post_via_webhook(channel: str, text: str, webhook_url: str) -> bool:
    if channel.startswith("U"):
        print(f"slack: no bot token configured — can't DM {channel} over a webhook, skipping")
        return False
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError as e:
        print(f"slack: webhook post failed: {e}")
        return False
    return True


def post(channel: str, text: str, token: str | None = None) -> bool:
    """Post `text` to `channel` (a channel ID, or a user ID for a DM — DMs
    need a bot token; see module docstring).

    Returns True on a 2xx response, False otherwise (including no
    notification method configured, or any network/API error) — never
    raises.
    """
    token = token if token is not None else os.environ.get("SLACK_BOT_TOKEN", "")
    if token:
        return _post_via_bot(channel, text, token)
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if webhook_url:
        return _post_via_webhook(channel, text, webhook_url)
    print("slack: neither SLACK_BOT_TOKEN nor SLACK_WEBHOOK_URL set, skipping post")
    return False


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python3 lib/slack.py <channel> <text>", file=sys.stderr)
        return 2
    ok = post(argv[1], argv[2])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
