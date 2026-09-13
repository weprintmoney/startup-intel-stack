"""SMTP send-queue processor. — the highest-stakes extraction:
this is the only node that sends real prospect email.

Extracted from smtp-send.yml's 141-line inline heredoc. Behavior-preserving,
including one subtle detail: the inter-send sleep only happens after an item
actually reaches smtp_send.send_email() and gets a result back — not for
items skipped earlier (malformed, LinkedIn-channel, not-due-yet, suppressed,
CRM-lookup-failed, paused/rejected/completed) and not when the daily cap
stops the batch.
"""

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crm  # noqa: E402
import slack  # noqa: E402
import smtp_send  # noqa: E402
import suppression  # noqa: E402


def _load_item(item_path: Path) -> dict | None:
    try:
        return json.loads(item_path.read_text())
    except Exception as e:
        print(f"Skipping {item_path}: {e}")
        return None


def _update_crm_after_send(item: dict, subject: str, today: str) -> None:
    contact_id = item.get("contact_id")
    if not contact_id:
        return
    touch_n = item.get("touch_number", 1)
    try:
        crm.set_field(contact_id, "last_touch_date", today)
        crm.set_field(contact_id, "last_touch_number", touch_n)
        if touch_n == 1:
            crm.set_field(contact_id, "sequence_status", "enrolled")
            crm.set_field(contact_id, "sequence_enrolled_date", today)
        crm.log_interaction(
            contact_id,
            f"Touch {touch_n} sent on {today}. Subject: {subject}. "
            f"From: {item.get('from_name') or '(default sender persona)'}.",
        )
    except Exception as e:
        print(f"CRM update warning: {e}")


def _alert_soft_bounce(to_email: str, error) -> None:
    channel = os.environ.get("SLACK_SALES_REVIEW_CHANNEL")
    if not channel:
        return
    slack.post(channel, f":warning: Soft bounce on send to `{to_email}`: {error}")


def process_item(item_path: Path, item: dict, *, today: str) -> dict | None:
    """Process one queue item. Returns a result dict to log, or None if
    nothing should be logged. Raises smtp_send.DailyCap when the daily cap
    is hit — the caller stops the batch without logging this item."""
    to_email = item.get("to")
    subject = item.get("subject")
    body = item.get("body")

    if not all([to_email, subject, body]):
        print(f"Skipping malformed queue item: {item_path.name}")
        return None

    # Safety: LinkedIn touches never go through email send
    if item.get("channel") == "linkedin":
        print(f"LinkedIn item in email queue, skipping: {item_path.name}")
        return None

    # Not due yet — leave in queue for a future run
    scheduled = item.get("scheduled_date", "")
    if scheduled and scheduled > today:
        return None

    if suppression.check(to_email):
        print(f"Suppressed, skipping: {to_email}")
        item_path.unlink()
        return None

    # Pause-on-reply: if the sequence is paused/rejected in CRM, cancel
    # this contact's remaining queued touches
    try:
        contact = crm.get_contact(to_email)
    except Exception as e:
        print(f"CRM lookup failed for {to_email}, skipping this run: {e}")
        return None
    # crm.get_contact() returns a normalized flat dict (see lib/crm.py) —
    # sequence_status is a plain top-level value, not nested per-provider.
    seq_status = (contact or {}).get("sequence_status", "")
    if seq_status in ("paused", "rejected", "completed"):
        print(f"Sequence {seq_status} for {to_email} — cancelling {item_path.name}")
        item_path.unlink()
        return None

    crm_bcc = os.environ.get("CRM_BCC_ADDRESS") or None
    result = smtp_send.send_email(
        to=to_email,
        subject=subject,
        body=body,
        from_name=item.get("from_name"),  # None -> configured sender persona
        body_html=item.get("body_html"),
        recipient_tz=item.get("recipient_tz"),  # None -> company.hq_timezone
        bcc=crm_bcc,
        reply_to=item.get("reply_to"),
    )
    # smtp_send.DailyCap propagates uncaught here — process_queue stops the
    # batch without logging this item, same as the original `break`.

    result["to"] = to_email
    result["item"] = item_path.name

    if result["success"]:
        print(f"Sent: {to_email}")
        _update_crm_after_send(item, subject, today)
        item_path.unlink()
    elif result.get("hard_bounce"):
        print(f"Hard bounce: {to_email}. Adding to suppression.")
        suppression.add(to_email, "bounced_hard", "smtp-send-workflow")
        item_path.unlink()
    else:
        print(f"Soft bounce / error for {to_email}: {result.get('error')}")
        _alert_soft_bounce(to_email, result.get("error"))

    return result


def process_queue(queue_dir: Path, log_dir: Path, *, today: str, sleep_fn=time.sleep) -> list[dict]:
    log_dir.mkdir(parents=True, exist_ok=True)
    queued = sorted(queue_dir.glob("*.json"))
    if not queued:
        print("No messages in queue.")
        return []

    results: list[dict] = []
    for item_path in queued:
        item = _load_item(item_path)
        if item is None:
            continue
        try:
            result = process_item(item_path, item, today=today)
        except smtp_send.DailyCap as e:
            print(f"Daily cap reached: {e}")
            break
        if result is not None:
            results.append(result)
            sleep_fn(smtp_send.SEND_INTERVAL_SECONDS)

    log_path = log_dir / f"{today}-sends.jsonl"
    with open(log_path, "a") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    print(f"Batch complete. {len(results)} processed.")
    return results


def main() -> int:
    process_queue(Path("sends/queue"), Path("sends/log"), today=date.today().isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
