"""Reply monitor: enforces Hard Rule 5 (pause on reply).

Extracted from reply-monitor.yml's 122-line inline heredoc. Behavior-
preserving: same unsubscribe-keyword detection, same CRM field updates,
same Slack DM/post routing. Uses lib.slack.post for both the DM and channel
paths instead of two near-duplicate inline urllib POSTs.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crm  # noqa: E402
import imap_poll  # noqa: E402
import slack  # noqa: E402
import suppression  # noqa: E402

UNSUBSCRIBE_KEYWORDS = ["unsubscribe", "opt out", "opt-out", "remove me", "take me off"]

# Slack user IDs to DM. OWNER_UID gets every unsubscribe + reply notice;
# ESCALATION_UID (e.g. a founder) additionally gets normal (non-unsubscribe)
# replies, since those need a human response. Both optional — set via env
# (people[] in company-profile.yaml has no Slack-ID field yet, so these
# aren't config-sourced). Empty values are skipped, not posted.
OWNER_UID = os.environ.get("REPLY_MONITOR_OWNER_UID", "")
ESCALATION_UID = os.environ.get("REPLY_MONITOR_ESCALATION_UID", "")


def _notify(uid: str, msg: str) -> None:
    if uid:
        slack.post(uid, msg)


def is_unsubscribe(reply: dict) -> bool:
    haystack = (reply.get("subject", "") + " " + reply.get("body_snippet", "")).lower()
    return any(kw in haystack for kw in UNSUBSCRIBE_KEYWORDS)


def extract_email(from_addr: str) -> str:
    """`Name <email@x.com>` -> `email@x.com`; a bare address passes through."""
    return from_addr.split("<")[-1].rstrip(">").strip() if "<" in from_addr else from_addr


def _record_id(contact: dict | None) -> str | None:
    # crm.get_contact() returns a normalized flat dict (see lib/crm.py) —
    # "id" is already a plain string, not a nested per-provider record shape.
    return contact.get("id") if contact else None


def handle_unsubscribe(email: str, record_id: str | None, from_addr: str, date_str: str) -> None:
    try:
        suppression.add(email, "unsubscribed", "reply-monitor")
        print(f"Suppressed (unsubscribe): {email}")
    except Exception as e:
        print(f"Suppression error: {e}")

    if record_id:
        try:
            crm.set_field(record_id, "suppressed", True)
            crm.set_field(record_id, "sequence_status", "paused")
            crm.log_interaction(
                record_id,
                f"Unsubscribe request received on {date_str}. Contact suppressed. Sequence stopped.",
            )
        except Exception as e:
            print(f"CRM update error: {e}")

    msg = (
        ":no_entry: *Unsubscribe request — contact suppressed*\n"
        f"  From: `{from_addr}`\n"
        f"  Date: {date_str}\n"
        "  Added to suppression list. No further sends."
    )
    _notify(OWNER_UID, msg)


def handle_normal_reply(
    email: str, record_id: str | None, from_addr: str, subject: str, date_str: str, channel: str
) -> None:
    if record_id:
        try:
            crm.set_field(record_id, "sequence_status", "paused")
            crm.set_field(record_id, "reply_received", True)
            crm.log_interaction(record_id, f"Reply received on {date_str}. Subject: {subject}. Sequence paused.")
            print(f"CRM: sequence paused for {email}")
        except Exception as e:
            print(f"CRM update error: {e}")

    msg = (
        ":email: *Reply received — sequence paused*\n"
        f"  From: `{from_addr}`\n"
        f"  Subject: _{subject}_\n"
        f"  Date: {date_str}\n"
        "  Sequence for this contact is now *paused*. Review and respond manually."
    )
    _notify(OWNER_UID, msg)
    _notify(ESCALATION_UID, msg)
    if channel:
        slack.post(channel, msg)


def process_reply(reply: dict, *, channel: str) -> None:
    from_addr = reply.get("from", "")
    subject = reply.get("subject", "")
    date_str = reply.get("date", "")
    print(f"Reply detected: {from_addr} — {subject}")

    email = extract_email(from_addr)
    contact = crm.get_contact(email)
    record_id = _record_id(contact)

    if is_unsubscribe(reply):
        handle_unsubscribe(email, record_id, from_addr, date_str)
    else:
        handle_normal_reply(email, record_id, from_addr, subject, date_str, channel)


def main() -> int:
    channel = os.environ.get("SLACK_SALES_REVIEW_CHANNEL", "")
    replies = imap_poll.check_replies(since_hours=2)
    if not replies:
        print("No new replies detected.")
        return 0
    for reply in replies:
        process_reply(reply, channel=channel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
