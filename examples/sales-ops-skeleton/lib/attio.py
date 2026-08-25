"""
Attio v2 API wrapper for the <YOUR_COMPANY> sales-ops pipeline.

Uses ATTIO_API_KEY environment variable. All operations target the
/objects/people endpoint. Raises on 4xx/5xx except 404 on get_contact
(which returns None).
"""

import os
import requests
from typing import Any

ATTIO_BASE = "https://api.attio.com/v2"


def _headers() -> dict:
    key = os.environ["ATTIO_API_KEY"]
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _raise_for_status(resp: requests.Response, allow_404: bool = False) -> None:
    if allow_404 and resp.status_code == 404:
        return
    if resp.status_code >= 400:
        raise requests.HTTPError(
            f"Attio API error {resp.status_code}: {resp.text}", response=resp
        )


def _query_people(filter_payload: dict) -> list[dict]:
    url = f"{ATTIO_BASE}/objects/people/records/query"
    resp = requests.post(url, headers=_headers(), json={"filter": filter_payload}, timeout=15)
    _raise_for_status(resp)
    return resp.json().get("data", [])


def search_by_name(name: str) -> list[dict]:
    """Search contacts by full name. Returns list of matching records."""
    parts = name.strip().split(" ", 1)
    if len(parts) > 1:
        f: dict = {"$and": [
            {"name": {"first_name": {"$eq": parts[0]}}},
            {"name": {"last_name":  {"$eq": parts[1]}}},
        ]}
    else:
        f = {"name": {"first_name": {"$eq": parts[0]}}}
    return _query_people(f)


def get_contact(email: str) -> dict | None:
    """Fetch a contact record by email. Returns None if not found."""
    data = _query_people({"email_addresses": {"email_address": {"$eq": email}}})
    return data[0] if data else None


def upsert_contact(data: dict) -> dict:
    """Create or update a contact. Returns the Attio record.

    data keys map to Attio attribute slugs. Standard keys expected:
    email, company_name, contact_title, icp_segment, sequence_status, etc.
    """
    email = data.get("email")
    if not email:
        raise ValueError("upsert_contact requires 'email' in data")

    existing = get_contact(email)

    # Build Attio attribute payload
    values: dict[str, Any] = {}
    if "email" in data:
        values["email_addresses"] = [{"email_address": data["email"]}]
    for field in (
        "company_name",
        "contact_title",
        "icp_segment",
        "sequence_status",
        "sequence_enrolled_date",
        "last_touch_date",
        "last_touch_number",
        "reply_received",
        "outreach_channel",
        "eu_contact",
        "suppressed",
        "approved_by",
        "pain_point",
        "vertical_proof",
        "touch_2_subject",
        "touch_2_scenario",
    ):
        if field in data:
            values[field] = data[field]
    # Map name fields — "name" is a personal-name composite in Attio
    if "contact_name" in data:
        parts = data["contact_name"].strip().split(" ", 1)
        values["name"] = [{
            "first_name": parts[0],
            "last_name":  parts[1] if len(parts) > 1 else "",
            "full_name":  data["contact_name"].strip(),
        }]

    payload = {"data": {"values": values}}

    if existing:
        record_id = existing["id"]["record_id"]
        url = f"{ATTIO_BASE}/objects/people/records/{record_id}"
        resp = requests.patch(url, headers=_headers(), json=payload, timeout=15)
        _raise_for_status(resp)
        return resp.json().get("data", {})
    else:
        url = f"{ATTIO_BASE}/objects/people/records"
        resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
        _raise_for_status(resp)
        return resp.json().get("data", {})


def log_interaction(contact_id: str, note: str) -> None:
    """Append a note to a contact record."""
    url = f"{ATTIO_BASE}/notes"
    payload = {
        "data": {
            "parent_object": "people",
            "parent_record_id": contact_id,
            "title": "Outreach interaction",
            "content": note,
        }
    }
    resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
    _raise_for_status(resp)


def set_field(contact_id: str, field: str, value: Any) -> None:
    """Update a single field on a contact record."""
    url = f"{ATTIO_BASE}/objects/people/records/{contact_id}"
    if field == "email":
        values = {"email_addresses": [{"email_address": value}]}
    else:
        values = {field: value}
    payload = {"data": {"values": values}}
    resp = requests.patch(url, headers=_headers(), json=payload, timeout=15)
    _raise_for_status(resp)
