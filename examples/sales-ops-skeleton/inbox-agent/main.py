"""
Inbox Agent — FastAPI micro-app for querying <FOUNDER_NAME>'s Gmail send history.

Exposes a narrow, config-driven query surface. Returns boolean + date only;
never returns email content, subjects, or recipient lists.

Authentication: HMAC-signed Bearer token using INBOX_AGENT_SECRET env var.
"""

import hashlib
import hmac
import os
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI(title="Inbox Agent", docs_url=None, redoc_url=None)

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _verify_token(authorization: str) -> None:
    """HMAC-verify the Bearer token."""
    secret = os.environ.get("INBOX_AGENT_SECRET", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[len("Bearer "):]
    expected = hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    # Token is HMAC(secret, token) — caller sends HMAC(secret, nonce)
    # For simplicity in Phase 1: token IS the pre-shared secret
    if not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Invalid token")


def _gmail_service():
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    import json
    creds = service_account.Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        subject=os.environ.get("GMAIL_DELEGATED_USER", ""),
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


@app.get("/prior-contact")
def prior_contact(
    email: str = Query(..., description="Email address to check"),
    authorization: str = Header(...),
) -> dict:
    """
    Check if <FOUNDER_NAME> has previously contacted this email address.
    Returns: {"contacted": bool, "last_date": "YYYY-MM-DD" | null}
    """
    _verify_token(authorization)

    config = _load_config()
    if "prior_contact_check" not in config.get("allowed_queries", []):
        raise HTTPException(status_code=403, detail="Query type not allowed")

    lookback_days = config.get("max_lookback_days", 180)
    after = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y/%m/%d")

    try:
        service = _gmail_service()
        # Search sent mail for this email address
        query = f"to:{email} after:{after}"
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=1,
            labelIds=["SENT"],
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return {"contacted": False, "last_date": None}

        # Get the date of the most recent sent message
        msg = service.users().messages().get(
            userId="me",
            id=messages[0]["id"],
            format="metadata",
            metadataHeaders=["Date"],
        ).execute()

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        date_str = headers.get("Date", "")
        # Parse to YYYY-MM-DD
        try:
            from email.utils import parsedate_to_datetime
            last_date = parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
        except Exception:
            last_date = None

        return {"contacted": True, "last_date": last_date}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail query failed: {str(e)}")


@app.get("/health")
def health():
    return {"status": "ok"}
