"""
Suppression list manager for the outbound pipeline.

Reads/writes suppression/list.jsonl (one JSON record per line).
Supports exact email match and domain wildcard match.

Hard rule: `check(email)` must be called before EVERY send.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

VALID_REASONS = {
    "bounced_hard",
    "unsubscribed",
    "complaint",
    "competitor",
    "internal",
    "gdpr_request",
    "prior_outreach",
}

DEFAULT_PATH = Path(__file__).parent.parent / "suppression" / "list.jsonl"


def _get_path() -> Path:
    env_path = os.environ.get("SUPPRESSION_LIST_PATH")
    return Path(env_path) if env_path else DEFAULT_PATH


def _load_records() -> list[dict]:
    path = _get_path()
    if not path.exists():
        return []
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def check(email: str) -> bool:
    """Return True if the email is suppressed (exact match or domain wildcard)."""
    email = email.lower().strip()
    domain = email.split("@", 1)[-1] if "@" in email else ""
    for record in _load_records():
        rec_email = (record.get("email") or "").lower().strip()
        rec_domain = (record.get("domain") or "").lower().strip()
        if rec_email and rec_email == email:
            return True
        if rec_domain and rec_domain == domain:
            return True
    return False


def add(
    email: str,
    reason: str,
    added_by: str = "system",
) -> None:
    """Append a new suppression record.

    Args:
        email: The email address to suppress, or "@domain.com" for a
            domain-wide block.
        reason: One of the valid reason codes.
        added_by: Who triggered the suppression (a username or 'system').
    """
    if reason not in VALID_REASONS:
        raise ValueError(f"Invalid reason '{reason}'. Must be one of: {VALID_REASONS}")

    email = email.lower().strip()
    domain: Optional[str] = None
    if email.startswith("@"):
        domain = email.lstrip("@")
        email_field = ""
    elif "@" in email:
        domain = None
        email_field = email
    else:
        raise ValueError(f"Invalid email or domain: '{email}'")

    record = {
        "email": email_field,
        "domain": domain,
        "reason": reason,
        "added_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "added_by": added_by,
    }

    path = _get_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")
