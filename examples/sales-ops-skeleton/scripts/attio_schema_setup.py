"""Idempotently provision the custom People attributes the sales-ops pipeline expects.

The pipeline stores per-lead sequencing state in Attio (sequence_status,
outreach_channel, pain_point, ...). These are custom attributes on the
People object. If they don't exist yet, `dedup-review.yml` fails at
upsert with `Cannot find attribute with slug/ID "..."`.

This script queries the People schema, computes the delta against the
declared schema below, and creates only the missing attributes. Run
with an Attio API key that has write scope on object attributes (admin).

Usage:
    ATTIO_API_KEY=... python scripts/attio_schema_setup.py [--dry-run]
"""

import argparse
import os
import sys
from typing import Any

import requests

ATTIO_BASE = "https://api.attio.com/v2"


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


# Declared schema. `title` is the human label; `api_slug` is what the
# pipeline sends. `type` maps to Attio's attribute-type strings.
#
# NOTE: the `icp_segment` enum options below are placeholders. Replace
# them with your own ICP segments from
# `internal-docs/03-commercial-revenue/icp-filter-criteria.yaml`
# before running this script (or load them from that YAML at runtime).
DESIRED_ATTRIBUTES: list[dict[str, Any]] = [
    {"title": "Company name",         "api_slug": "company_name",          "type": "text"},
    {"title": "Contact title",        "api_slug": "contact_title",         "type": "text"},
    {"title": "ICP segment",          "api_slug": "icp_segment",           "type": "select",
     "options": ["segment-a", "segment-b", "segment-c"]},
    {"title": "Sequence status",      "api_slug": "sequence_status",       "type": "status",
     "options": ["pending", "enrolled", "completed", "paused", "rejected"]},
    {"title": "Sequence enrolled",    "api_slug": "sequence_enrolled_date","type": "date"},
    {"title": "Last touch date",      "api_slug": "last_touch_date",       "type": "date"},
    {"title": "Last touch number",    "api_slug": "last_touch_number",     "type": "number"},
    {"title": "Reply received",       "api_slug": "reply_received",        "type": "checkbox"},
    {"title": "Outreach channel",     "api_slug": "outreach_channel",      "type": "select",
     "options": ["email", "linkedin_only"]},
    {"title": "EU contact",           "api_slug": "eu_contact",            "type": "checkbox"},
    {"title": "Suppressed",           "api_slug": "suppressed",            "type": "checkbox"},
    {"title": "Approved by",          "api_slug": "approved_by",           "type": "text"},
    {"title": "Pain point",           "api_slug": "pain_point",            "type": "text"},
    {"title": "Vertical proof",       "api_slug": "vertical_proof",        "type": "text"},
    {"title": "Touch 2 subject",      "api_slug": "touch_2_subject",       "type": "text"},
    {"title": "Touch 2 scenario",     "api_slug": "touch_2_scenario",      "type": "text"},
]


def get_existing_slugs(key: str) -> set[str]:
    r = requests.get(f"{ATTIO_BASE}/objects/people/attributes", headers=_headers(key), timeout=15)
    r.raise_for_status()
    return {a["api_slug"] for a in r.json().get("data", [])}


def build_payload(attr: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "data": {
            "title":       attr["title"],
            "api_slug":    attr["api_slug"],
            "type":        attr["type"],
            "is_multiselect": False,
            "is_required": False,
            "is_unique":   False,
            "default_value": None,
        }
    }
    if attr["type"] in ("select", "status") and attr.get("options"):
        body["data"]["config"] = {
            "options": [{"title": o} for o in attr["options"]],
        }
    return body


def create_attribute(key: str, attr: dict[str, Any]) -> None:
    r = requests.post(
        f"{ATTIO_BASE}/objects/people/attributes",
        headers=_headers(key),
        json=build_payload(attr),
        timeout=15,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code}: {r.text}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    key = os.environ.get("ATTIO_API_KEY")
    if not key:
        print("ATTIO_API_KEY not set", file=sys.stderr)
        return 2

    existing = get_existing_slugs(key)
    print(f"Existing People attributes ({len(existing)}): {sorted(existing)}")

    missing = [a for a in DESIRED_ATTRIBUTES if a["api_slug"] not in existing]
    print(f"\nMissing attributes ({len(missing)}):")
    for a in missing:
        print(f"  - {a['api_slug']} ({a['type']})")

    if not missing:
        print("\nSchema is already provisioned.")
        return 0

    if args.dry_run:
        print("\n--dry-run: no changes made.")
        return 0

    print()
    created, failed = [], []
    for a in missing:
        try:
            create_attribute(key, a)
            print(f"  + created {a['api_slug']}")
            created.append(a["api_slug"])
        except Exception as e:
            print(f"  ! FAILED {a['api_slug']}: {e}")
            failed.append((a["api_slug"], str(e)))

    print(f"\nCreated: {len(created)}, Failed: {len(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
