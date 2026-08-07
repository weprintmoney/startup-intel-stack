"""
IMAP reply monitor for the outbound pipeline.

Polls the INBOX for replies to our outreach emails. A "reply" is defined as
any email whose In-Reply-To or References header matches a Message-ID from
emails sent by the outreach mailbox.

Mailbox parameters come entirely from environment variables (set from GitHub
secrets by the reply-monitor workflow — nothing is hardcoded here):
  IMAP_HOST      IMAP server, e.g. imap.gmail.com
  IMAP_USER      the outreach mailbox address (also the login user)
  IMAP_PASSWORD  app password / IMAP password

Uses stdlib only: imaplib + email.
"""

import email
import imaplib
import os
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from typing import Optional

from email.utils import parsedate_to_datetime


def _outreach_address() -> str:
    addr = os.environ.get("IMAP_USER", "")
    if not addr:
        raise RuntimeError("IMAP_USER env var not set (outreach mailbox address)")
    return addr


def _decode_header_value(value: Optional[str]) -> str:
    if not value:
        return ""
    decoded_parts = decode_header(value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def _get_sent_message_ids(conn: imaplib.IMAP4_SSL, since_dt: datetime) -> set[str]:
    """Collect Message-IDs from our Sent folder for the given time window."""
    sent_message_ids: set[str] = set()
    since_str = since_dt.strftime("%d-%b-%Y")
    outreach = _outreach_address()

    for folder in ("[Gmail]/Sent Mail", "Sent", "Sent Items", "INBOX.Sent"):
        try:
            status, _ = conn.select(folder, readonly=True)
            if status != "OK":
                continue
            _, data = conn.search(None, f'(SINCE "{since_str}" FROM "{outreach}")')
            if not data or not data[0]:
                continue
            uids = data[0].split()
            for uid in uids:
                _, msg_data = conn.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
                if not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1]
                if isinstance(raw, bytes):
                    parsed = email.message_from_bytes(raw)
                else:
                    parsed = email.message_from_string(raw)
                mid = parsed.get("Message-ID", "").strip()
                if mid:
                    sent_message_ids.add(mid)
            break  # found the right Sent folder
        except (imaplib.IMAP4.error, Exception):
            continue
    return sent_message_ids


def check_replies(since_hours: int = 2) -> list[dict]:
    """Poll INBOX for replies to our outreach emails.

    Returns a list of dicts:
        {"from": str, "subject": str, "date": str, "message_id": str,
         "body_snippet": str}

    Only emails whose In-Reply-To / References headers reference a message
    we actually sent are included.
    """
    imap_host = os.environ["IMAP_HOST"]
    imap_password = os.environ["IMAP_PASSWORD"]
    outreach = _outreach_address()

    since_dt = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    since_str = since_dt.strftime("%d-%b-%Y")

    replies: list[dict] = []

    with imaplib.IMAP4_SSL(imap_host) as conn:
        conn.login(outreach, imap_password)

        # Collect sent Message-IDs (look back further to catch all threads)
        sent_window = datetime.now(timezone.utc) - timedelta(days=60)
        sent_ids = _get_sent_message_ids(conn, sent_window)

        # Now search INBOX for recent messages
        conn.select("INBOX", readonly=True)
        _, data = conn.search(None, f'(SINCE "{since_str}")')
        if not data or not data[0]:
            return []

        uids = data[0].split()
        for uid in uids:
            _, msg_data = conn.fetch(uid, "(BODY.PEEK[])")
            if not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            if isinstance(raw, bytes):
                parsed = email.message_from_bytes(raw)
            else:
                parsed = email.message_from_string(raw)

            in_reply_to = parsed.get("In-Reply-To", "").strip()
            references = parsed.get("References", "").strip()
            ref_ids = set(references.split()) | ({in_reply_to} if in_reply_to else set())

            if not ref_ids.intersection(sent_ids):
                continue  # not a reply to our outreach

            from_addr = _decode_header_value(parsed.get("From"))
            subject = _decode_header_value(parsed.get("Subject"))
            date_raw = parsed.get("Date", "")
            try:
                date_str = parsedate_to_datetime(date_raw).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                date_str = date_raw
            message_id = parsed.get("Message-ID", "").strip()

            # Extract plain-text body snippet for keyword detection
            body_snippet = ""
            if parsed.is_multipart():
                for part in parsed.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body_snippet = part.get_payload(decode=True).decode(
                                part.get_content_charset() or "utf-8", errors="replace"
                            )[:500]
                        except Exception:
                            pass
                        break
            else:
                try:
                    body_snippet = parsed.get_payload(decode=True).decode(
                        parsed.get_content_charset() or "utf-8", errors="replace"
                    )[:500]
                except Exception:
                    pass

            replies.append(
                {
                    "from": from_addr,
                    "subject": subject,
                    "date": date_str,
                    "message_id": message_id,
                    "body_snippet": body_snippet,
                }
            )

    return replies
