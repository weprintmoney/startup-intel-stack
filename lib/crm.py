"""
CRM adapter for the outbound pipeline.

Backend is selected by `crm.provider` in company-profile.yaml (override with
the CRM_PROVIDER env var):

  attio    -> Attio v2 API (people object). API key from CRM_API_KEY
              (fallback: ATTIO_API_KEY).
  airtable -> Airtable REST API. API key from CRM_API_KEY (fallback:
              AIRTABLE_API_KEY); base from AIRTABLE_BASE_ID; table from
              AIRTABLE_TABLE (default "Contacts").
  none     -> local JSONL store under leads/crm-local/ — zero-dependency
              default so the pipeline works with no CRM at all.

All backends implement the same interface and return NORMALIZED contact
dicts: {"id": str, "email": str, <field>: <plain value>, ...}. Callers never
see provider-specific record shapes.

Pipeline state fields (the sequence state machine lives on these):
  email, contact_name, company_name, contact_title, linkedin_url, icp_segment,
  sequence_status (pending|enrolled|completed|paused|rejected),
  sequence_enrolled_date, last_touch_date, last_touch_number,
  reply_received, outreach_channel (email|linkedin_only), eu_contact,
  suppressed
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

CONTACT_FIELDS = [
    "email",
    "contact_name",
    "company_name",
    "contact_title",
    "linkedin_url",
    "icp_segment",
    "sequence_status",
    "sequence_enrolled_date",
    "last_touch_date",
    "last_touch_number",
    "reply_received",
    "outreach_channel",
    "eu_contact",
    "suppressed",
]

LOCAL_STORE_DIR = Path(
    os.environ.get("CRM_LOCAL_DIR")
    or Path(__file__).parent.parent / "leads" / "crm-local"
)


def _provider() -> str:
    provider = os.environ.get("CRM_PROVIDER")
    if provider:
        return provider
    try:
        import config
        return config.get("crm.provider", "none") or "none"
    except Exception:
        return "none"


def _api_key(*fallbacks: str) -> str:
    for var in ("CRM_API_KEY", *fallbacks):
        key = os.environ.get(var)
        if key:
            return key
    raise RuntimeError(
        "No CRM API key found. Set CRM_API_KEY (the workflow maps the secret "
        "named by crm.api_key_secret in company-profile.yaml)."
    )


# ---------------------------------------------------------------------------
# Attio backend
# ---------------------------------------------------------------------------

class _AttioBackend:
    BASE = "https://api.attio.com/v2"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {_api_key('ATTIO_API_KEY')}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _raise_for_status(self, resp, allow_404: bool = False) -> None:
        import requests
        if allow_404 and resp.status_code == 404:
            return
        if resp.status_code >= 400:
            raise requests.HTTPError(
                f"Attio API error {resp.status_code}: {resp.text}", response=resp
            )

    def _query_people(self, filter_payload: dict) -> list[dict]:
        import requests
        url = f"{self.BASE}/objects/people/records/query"
        resp = requests.post(
            url, headers=self._headers(), json={"filter": filter_payload}, timeout=15
        )
        self._raise_for_status(resp)
        return resp.json().get("data", [])

    @staticmethod
    def _flatten(record: dict) -> dict:
        """Normalize an Attio record to a flat contact dict."""
        out: dict[str, Any] = {
            "id": record.get("id", {}).get("record_id", "")
        }
        values = record.get("values", {}) or {}
        for slug, entries in values.items():
            if not isinstance(entries, list) or not entries:
                continue
            entry = entries[0]
            if not isinstance(entry, dict):
                out[slug] = entry
                continue
            if slug == "email_addresses":
                out["email"] = entry.get("email_address", "")
            elif slug == "name":
                out["contact_name"] = entry.get("full_name", "")
            else:
                # Attio value dicts carry the payload under one of these keys
                for k in ("value", "status", "option"):
                    if k in entry:
                        v = entry[k]
                        if isinstance(v, dict):
                            v = v.get("title", v.get("value", ""))
                        out[slug] = v
                        break
        return out

    def search_by_name(self, name: str) -> list[dict]:
        parts = name.strip().split(" ", 1)
        if len(parts) > 1:
            f: dict = {"$and": [
                {"name": {"first_name": {"$eq": parts[0]}}},
                {"name": {"last_name": {"$eq": parts[1]}}},
            ]}
        else:
            f = {"name": {"first_name": {"$eq": parts[0]}}}
        return [self._flatten(r) for r in self._query_people(f)]

    def get_contact(self, email: str) -> Optional[dict]:
        data = self._query_people(
            {"email_addresses": {"email_address": {"$eq": email}}}
        )
        return self._flatten(data[0]) if data else None

    def _values_payload(self, data: dict) -> dict:
        values: dict[str, Any] = {}
        if "email" in data:
            values["email_addresses"] = [{"email_address": data["email"]}]
        for field in CONTACT_FIELDS:
            if field in ("email", "contact_name"):
                continue
            if field in data:
                values[field] = data[field]
        if "contact_name" in data and data["contact_name"]:
            parts = data["contact_name"].strip().split(" ", 1)
            values["name"] = [{
                "first_name": parts[0],
                "last_name": parts[1] if len(parts) > 1 else "",
                "full_name": data["contact_name"].strip(),
            }]
        return values

    def upsert_contact(self, data: dict) -> dict:
        import requests
        email = data.get("email")
        if not email:
            raise ValueError("upsert_contact requires 'email' in data")
        existing = self.get_contact(email)
        payload = {"data": {"values": self._values_payload(data)}}
        if existing:
            url = f"{self.BASE}/objects/people/records/{existing['id']}"
            resp = requests.patch(url, headers=self._headers(), json=payload, timeout=15)
        else:
            url = f"{self.BASE}/objects/people/records"
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=15)
        self._raise_for_status(resp)
        return self._flatten(resp.json().get("data", {}))

    def set_field(self, contact_id: str, field: str, value: Any) -> None:
        import requests
        url = f"{self.BASE}/objects/people/records/{contact_id}"
        if field == "email":
            values: dict = {"email_addresses": [{"email_address": value}]}
        else:
            values = {field: value}
        resp = requests.patch(
            url, headers=self._headers(), json={"data": {"values": values}}, timeout=15
        )
        self._raise_for_status(resp)

    def log_interaction(self, contact_id: str, note: str) -> None:
        import requests
        url = f"{self.BASE}/notes"
        payload = {
            "data": {
                "parent_object": "people",
                "parent_record_id": contact_id,
                "title": "Outreach interaction",
                "content": note,
            }
        }
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=15)
        self._raise_for_status(resp)


# ---------------------------------------------------------------------------
# Airtable backend
# ---------------------------------------------------------------------------

class _AirtableBackend:
    def __init__(self):
        self.base_id = os.environ.get("AIRTABLE_BASE_ID", "")
        self.table = os.environ.get("AIRTABLE_TABLE", "Contacts")
        if not self.base_id:
            raise RuntimeError("AIRTABLE_BASE_ID env var not set")

    def _url(self, suffix: str = "") -> str:
        return f"https://api.airtable.com/v0/{self.base_id}/{self.table}{suffix}"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {_api_key('AIRTABLE_API_KEY')}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _flatten(record: dict) -> dict:
        out = {"id": record.get("id", "")}
        out.update(record.get("fields", {}) or {})
        return out

    def _query(self, formula: str) -> list[dict]:
        import requests
        resp = requests.get(
            self._url(), headers=self._headers(),
            params={"filterByFormula": formula, "maxRecords": 10}, timeout=15,
        )
        resp.raise_for_status()
        return [self._flatten(r) for r in resp.json().get("records", [])]

    def search_by_name(self, name: str) -> list[dict]:
        safe = name.replace('"', '\\"').strip()
        return self._query(f'LOWER({{contact_name}}) = LOWER("{safe}")')

    def get_contact(self, email: str) -> Optional[dict]:
        safe = email.replace('"', '\\"').strip()
        records = self._query(f'LOWER({{email}}) = LOWER("{safe}")')
        return records[0] if records else None

    def upsert_contact(self, data: dict) -> dict:
        import requests
        email = data.get("email")
        if not email:
            raise ValueError("upsert_contact requires 'email' in data")
        fields = {k: v for k, v in data.items() if k in CONTACT_FIELDS}
        existing = self.get_contact(email)
        if existing:
            resp = requests.patch(
                self._url(f"/{existing['id']}"), headers=self._headers(),
                json={"fields": fields}, timeout=15,
            )
        else:
            resp = requests.post(
                self._url(), headers=self._headers(),
                json={"fields": fields}, timeout=15,
            )
        resp.raise_for_status()
        return self._flatten(resp.json())

    def set_field(self, contact_id: str, field: str, value: Any) -> None:
        import requests
        resp = requests.patch(
            self._url(f"/{contact_id}"), headers=self._headers(),
            json={"fields": {field: value}}, timeout=15,
        )
        resp.raise_for_status()

    def log_interaction(self, contact_id: str, note: str) -> None:
        """Airtable has no notes API — append to an interactions_log field."""
        import requests
        resp = requests.get(self._url(f"/{contact_id}"), headers=self._headers(), timeout=15)
        resp.raise_for_status()
        existing = (resp.json().get("fields", {}) or {}).get("interactions_log", "")
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        updated = (existing + "\n" if existing else "") + f"[{stamp}] {note}"
        self.set_field(contact_id, "interactions_log", updated)


# ---------------------------------------------------------------------------
# Local (no-CRM) backend — JSONL store under leads/crm-local/
# ---------------------------------------------------------------------------

class _LocalBackend:
    """Same interface, no external service. Contacts live one-JSON-per-line
    in leads/crm-local/contacts.jsonl; interactions append to
    leads/crm-local/interactions.jsonl. Data stays in the instance repo."""

    @property
    def contacts_path(self) -> Path:
        return LOCAL_STORE_DIR / "contacts.jsonl"

    @property
    def interactions_path(self) -> Path:
        return LOCAL_STORE_DIR / "interactions.jsonl"

    def _load(self) -> list[dict]:
        if not self.contacts_path.exists():
            return []
        records = []
        for line in self.contacts_path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return records

    def _save(self, records: list[dict]) -> None:
        LOCAL_STORE_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.contacts_path, "w") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def search_by_name(self, name: str) -> list[dict]:
        needle = name.lower().strip()
        return [
            r for r in self._load()
            if (r.get("contact_name") or "").lower().strip() == needle
        ]

    def get_contact(self, email: str) -> Optional[dict]:
        needle = email.lower().strip()
        for r in self._load():
            if (r.get("email") or "").lower().strip() == needle:
                return r
        return None

    def upsert_contact(self, data: dict) -> dict:
        email = data.get("email")
        if not email:
            raise ValueError("upsert_contact requires 'email' in data")
        records = self._load()
        needle = email.lower().strip()
        for r in records:
            if (r.get("email") or "").lower().strip() == needle:
                r.update({k: v for k, v in data.items() if k in CONTACT_FIELDS})
                self._save(records)
                return r
        record = {"id": needle, **{k: v for k, v in data.items() if k in CONTACT_FIELDS}}
        records.append(record)
        self._save(records)
        return record

    def set_field(self, contact_id: str, field: str, value: Any) -> None:
        records = self._load()
        for r in records:
            if r.get("id") == contact_id:
                r[field] = value
                self._save(records)
                return
        raise KeyError(f"No local contact with id {contact_id}")

    def log_interaction(self, contact_id: str, note: str) -> None:
        LOCAL_STORE_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.interactions_path, "a") as f:
            f.write(json.dumps({
                "contact_id": contact_id,
                "note": note,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Module-level interface — dispatches to the configured backend
# ---------------------------------------------------------------------------

_BACKENDS = {"attio": _AttioBackend, "airtable": _AirtableBackend, "none": _LocalBackend}
_backend_instance = None


def _backend():
    global _backend_instance
    if _backend_instance is None:
        provider = _provider()
        cls = _BACKENDS.get(provider)
        if cls is None:
            raise RuntimeError(
                f"Unknown crm.provider '{provider}' — expected one of {sorted(_BACKENDS)}"
            )
        _backend_instance = cls()
    return _backend_instance


def search_by_name(name: str) -> list[dict]:
    """Search contacts by full name. Returns normalized records."""
    return _backend().search_by_name(name)


def get_contact(email: str) -> Optional[dict]:
    """Fetch a contact by email. Returns a normalized dict or None."""
    return _backend().get_contact(email)


def upsert_contact(data: dict) -> dict:
    """Create or update a contact keyed on 'email'."""
    return _backend().upsert_contact(data)


def set_field(contact_id: str, field: str, value: Any) -> None:
    """Update one field on a contact record."""
    _backend().set_field(contact_id, field, value)


def log_interaction(contact_id: str, note: str) -> None:
    """Append a timestamped note to a contact's history."""
    _backend().log_interaction(contact_id, note)
