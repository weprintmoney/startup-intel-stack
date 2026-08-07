"""
Provider-agnostic outbound email sender.

All company-specific parameters come from company-profile.yaml:
- provider:      sending.provider   (resend | sendgrid | mailgun)
- daily cap:     sending.daily_cap  (hard limit; DailyCap raised when hit)
- send window:   sending.send_window (business days/hours, recipient-local)
- send domain:   company.send_domain

Hard constraints (never relax these):
- Refuses to send if send_domain equals the primary company.domain, or if the
  from-address is on the primary domain. Outbound NEVER goes out from the
  primary domain.
- Daily cap enforced via sends/daily-count.json (committed by the workflow).
- Sends only within the configured business-hours window in the recipient's
  timezone (falls back to company.hq_timezone).
- Exposes SEND_INTERVAL_SECONDS; the caller is responsible for sleeping
  between sends.

Provider API keys come from environment:
  resend   -> RESEND_API_KEY
  sendgrid -> SENDGRID_API_KEY
  mailgun  -> MAILGUN_API_KEY
Override the from-address with SEND_FROM; default is outreach@{send_domain}.
"""

import json
import os
import random
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import config

SEND_INTERVAL_SECONDS = random.uniform(180, 480)  # 3-8 min between sends

DAILY_COUNT_PATH = Path(
    os.environ.get("SEND_COUNT_PATH")
    or Path(__file__).parent.parent / "sends" / "daily-count.json"
)

_DAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


class DailyCap(Exception):
    """Raised when the configured daily send cap has been reached."""


class UnsafeSendDomain(Exception):
    """Raised when a send would go out from the primary company domain."""


def _load_daily_count() -> dict:
    if DAILY_COUNT_PATH.exists():
        with open(DAILY_COUNT_PATH) as f:
            return json.load(f)
    return {"date": "", "count": 0}


def _save_daily_count(record: dict) -> None:
    DAILY_COUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DAILY_COUNT_PATH, "w") as f:
        json.dump(record, f)


def _check_and_increment_daily_count(daily_cap: int) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    record = _load_daily_count()
    if record.get("date") != today:
        record = {"date": today, "count": 0}
    if record["count"] >= daily_cap:
        raise DailyCap(f"Daily send cap of {daily_cap} reached for {today}")
    record["count"] += 1
    _save_daily_count(record)


def _parse_days(days_spec: str) -> set[int]:
    """Parse 'Mon-Fri' or 'Mon,Wed,Fri' into weekday ints."""
    days_spec = (days_spec or "Mon-Fri").strip().lower()
    if "-" in days_spec:
        start_s, end_s = [d.strip()[:3] for d in days_spec.split("-", 1)]
        start, end = _DAY_INDEX.get(start_s, 0), _DAY_INDEX.get(end_s, 4)
        if start <= end:
            return set(range(start, end + 1))
        return set(range(start, 7)) | set(range(0, end + 1))
    return {_DAY_INDEX[d.strip()[:3]] for d in days_spec.split(",") if d.strip()[:3] in _DAY_INDEX}


def _parse_hour(value: str, default: int) -> int:
    try:
        return int(str(value).split(":")[0])
    except (ValueError, AttributeError):
        return default


def _is_business_hours(tz_name: str, profile: dict) -> bool:
    window = config.get("sending.send_window", {}, profile) or {}
    days = _parse_days(window.get("days", "Mon-Fri"))
    start = _parse_hour(window.get("start", "08:00"), 8)
    end = _parse_hour(window.get("end", "18:00"), 18)
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(config.get("company.hq_timezone", "UTC", profile))
    now = datetime.now(tz)
    return now.weekday() in days and start <= now.hour < end


def _from_address(profile: dict) -> str:
    send_domain = config.get("company.send_domain", "", profile)
    return os.environ.get("SEND_FROM") or f"outreach@{send_domain}"


def _assert_safe_domain(profile: dict, from_address: str) -> None:
    """Never send from the primary domain. This is a hard rule."""
    domain = (config.get("company.domain", "", profile) or "").lower().strip()
    send_domain = (config.get("company.send_domain", "", profile) or "").lower().strip()
    if not send_domain:
        raise UnsafeSendDomain("company.send_domain is not set in company-profile.yaml")
    if domain and send_domain == domain:
        raise UnsafeSendDomain(
            f"send_domain ({send_domain}) must differ from the primary domain ({domain})"
        )
    from_domain = from_address.split("@", 1)[-1].lower().strip()
    if domain and from_domain == domain:
        raise UnsafeSendDomain(
            f"Refusing to send from primary domain address {from_address}"
        )


def _send_resend(payload: dict, from_addr: str, from_name: str) -> requests.Response:
    api_key = os.environ["RESEND_API_KEY"]
    body = {
        "from": f"{from_name} <{from_addr}>",
        "to": [payload["to"]],
        "subject": payload["subject"],
        "text": payload["text"],
    }
    if payload.get("html"):
        body["html"] = payload["html"]
    if payload.get("bcc"):
        body["bcc"] = [payload["bcc"]]
    return requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )


def _send_sendgrid(payload: dict, from_addr: str, from_name: str) -> requests.Response:
    api_key = os.environ["SENDGRID_API_KEY"]
    personalization: dict = {"to": [{"email": payload["to"]}]}
    if payload.get("bcc"):
        personalization["bcc"] = [{"email": payload["bcc"]}]
    content = [{"type": "text/plain", "value": payload["text"]}]
    if payload.get("html"):
        content.append({"type": "text/html", "value": payload["html"]})
    body = {
        "personalizations": [personalization],
        "from": {"email": from_addr, "name": from_name},
        "subject": payload["subject"],
        "content": content,
    }
    return requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )


def _send_mailgun(payload: dict, from_addr: str, from_name: str, send_domain: str) -> requests.Response:
    api_key = os.environ["MAILGUN_API_KEY"]
    data = {
        "from": f"{from_name} <{from_addr}>",
        "to": payload["to"],
        "subject": payload["subject"],
        "text": payload["text"],
    }
    if payload.get("html"):
        data["html"] = payload["html"]
    if payload.get("bcc"):
        data["bcc"] = payload["bcc"]
    return requests.post(
        f"https://api.mailgun.net/v3/{send_domain}/messages",
        auth=("api", api_key),
        data=data,
        timeout=30,
    )


def send_email(
    to: str,
    subject: str,
    body: str,
    from_name: Optional[str] = None,
    body_html: Optional[str] = None,
    recipient_tz: Optional[str] = None,
    bcc: Optional[str] = None,
) -> dict:
    """Send an email via the configured provider.

    Returns:
        {"success": bool, "error": str | None, "smtp_code": int | None,
         "hard_bounce": bool}
    Raises:
        DailyCap if the configured daily cap is reached.
        UnsafeSendDomain if the send would leave from the primary domain.
    """
    profile = config.load()
    provider = config.get("sending.provider", "resend", profile)
    daily_cap = int(config.get("sending.daily_cap", 100, profile))
    from_addr = _from_address(profile)
    if from_name is None:
        from_name = config.sender_persona(profile)["name"]
    if recipient_tz is None:
        recipient_tz = config.get("company.hq_timezone", "UTC", profile)

    _assert_safe_domain(profile, from_addr)

    if not _is_business_hours(recipient_tz, profile):
        return {
            "success": False,
            "error": f"Outside business hours for timezone {recipient_tz}",
            "smtp_code": None,
            "hard_bounce": False,
        }

    _check_and_increment_daily_count(daily_cap)

    payload = {"to": to, "subject": subject, "text": body, "html": body_html, "bcc": bcc}

    try:
        if provider == "resend":
            resp = _send_resend(payload, from_addr, from_name)
        elif provider == "sendgrid":
            resp = _send_sendgrid(payload, from_addr, from_name)
        elif provider == "mailgun":
            send_domain = config.get("company.send_domain", "", profile)
            resp = _send_mailgun(payload, from_addr, from_name, send_domain)
        else:
            return {
                "success": False,
                "error": f"Unknown sending.provider '{provider}' in company-profile.yaml",
                "smtp_code": None,
                "hard_bounce": False,
            }
    except KeyError as e:
        return {
            "success": False,
            "error": f"Missing API key env var for provider '{provider}': {e}",
            "smtp_code": None,
            "hard_bounce": False,
        }
    except requests.RequestException as e:
        return {"success": False, "error": str(e), "smtp_code": None, "hard_bounce": False}

    if resp.status_code in (200, 202):
        return {"success": True, "error": None, "smtp_code": resp.status_code, "hard_bounce": False}

    # 4xx = permanent failure; 5xx = transient
    hard = resp.status_code < 500
    return {
        "success": False,
        "error": resp.text,
        "smtp_code": resp.status_code,
        "hard_bounce": hard,
    }
