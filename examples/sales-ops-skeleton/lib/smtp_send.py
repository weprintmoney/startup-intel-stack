"""
Email sender for the <YOUR_COMPANY> sales-ops pipeline. Uses the Resend API.

Hard constraints:
- Max 100 emails/day (DailyCap exception if exceeded)
- Sends only from mail.example.com subdomain
- Enforces business hours in recipient's timezone (falls back to US/CT)
- Exposes SEND_INTERVAL_SECONDS constant; caller is responsible for sleeping
"""

import json
import os
import random
import requests
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Optional

DAILY_CAP = 100
SEND_INTERVAL_SECONDS = random.uniform(180, 480)  # 3–8 min between sends

DAILY_COUNT_PATH = Path(__file__).parent.parent / "sends" / "daily-count.json"
RESEND_API_URL = "https://api.resend.com/emails"
FROM_ADDRESS = os.environ.get("RESEND_FROM", "outreach@mail.example.com")

BUSINESS_HOURS_START = 8   # 08:00 local
BUSINESS_HOURS_END = 18    # 18:00 local
BUSINESS_DAYS = {0, 1, 2, 3, 4}  # Mon–Fri


class DailyCap(Exception):
    """Raised when the daily send cap of 100 has been reached."""


def _load_daily_count() -> dict:
    if DAILY_COUNT_PATH.exists():
        with open(DAILY_COUNT_PATH) as f:
            return json.load(f)
    return {"date": "", "count": 0}


def _save_daily_count(record: dict) -> None:
    DAILY_COUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DAILY_COUNT_PATH, "w") as f:
        json.dump(record, f)


def _check_and_increment_daily_count() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    record = _load_daily_count()
    if record.get("date") != today:
        record = {"date": today, "count": 0}
    if record["count"] >= DAILY_CAP:
        raise DailyCap(f"Daily send cap of {DAILY_CAP} reached for {today}")
    record["count"] += 1
    _save_daily_count(record)


def _is_business_hours(tz_name: str) -> bool:
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, Exception):
        tz = ZoneInfo("America/Chicago")
    now = datetime.now(tz)
    return (
        now.weekday() in BUSINESS_DAYS
        and BUSINESS_HOURS_START <= now.hour < BUSINESS_HOURS_END
    )


def send_email(
    to: str,
    subject: str,
    body: str,
    from_name: str = "<FOUNDER_NAME>",
    body_html: Optional[str] = None,
    recipient_tz: str = "America/Chicago",
    bcc: Optional[str] = None,
) -> dict:
    """Send an email via the Resend API.

    Returns:
        {"success": bool, "error": str | None, "smtp_code": int | None,
         "hard_bounce": bool}
    """
    api_key = os.environ["RESEND_API_KEY"]

    # Safety: never send from main domain
    if "@example.com" in FROM_ADDRESS and "@mail.example.com" not in FROM_ADDRESS:
        return {
            "success": False,
            "error": "Refusing to send from main example.com domain. Use mail.example.com.",
            "smtp_code": None,
            "hard_bounce": False,
        }

    if not _is_business_hours(recipient_tz):
        return {
            "success": False,
            "error": f"Outside business hours for timezone {recipient_tz}",
            "smtp_code": None,
            "hard_bounce": False,
        }

    _check_and_increment_daily_count()

    payload: dict = {
        "from": f"{from_name} <{FROM_ADDRESS}>",
        "to": [to],
        "subject": subject,
        "text": body,
    }
    if body_html:
        payload["html"] = body_html
    if bcc:
        payload["bcc"] = [bcc]

    try:
        resp = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
    except requests.RequestException as e:
        return {"success": False, "error": str(e), "smtp_code": None, "hard_bounce": False}

    if resp.status_code == 200:
        return {"success": True, "error": None, "smtp_code": 200, "hard_bounce": False}

    # 4xx = permanent failure; 5xx = transient
    hard = resp.status_code < 500
    return {
        "success": False,
        "error": resp.text,
        "smtp_code": resp.status_code,
        "hard_bounce": hard,
    }
