"""Tiny helper that loads company-profile.yaml — the single source of
company-specific parameters for every agent and library in this repo.

Usage:
    import config
    profile = config.load()
    cap = config.get("sending.daily_cap", 100)
    if not config.stage_at_least("seed"):
        sys.exit(0)
"""

import os
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).parent.parent / "company-profile.yaml"

STAGE_ORDER = ["pre-seed", "seed", "series-a"]


def load(path: str | None = None) -> dict:
    """Load and parse company-profile.yaml. Override the path with the
    COMPANY_PROFILE_PATH env var (useful in tests)."""
    p = Path(path or os.environ.get("COMPANY_PROFILE_PATH") or DEFAULT_PATH)
    if not p.exists():
        raise FileNotFoundError(
            f"company-profile.yaml not found at {p} — run /gtm-init first."
        )
    with open(p) as f:
        return yaml.safe_load(f) or {}


def get(dotted_key: str, default=None, profile: dict | None = None):
    """Fetch a value by dotted path, e.g. get('sending.daily_cap', 100)."""
    node = profile if profile is not None else load()
    for key in dotted_key.split("."):
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node if node is not None else default


def stage_at_least(required: str, profile: dict | None = None) -> bool:
    """True if company.stage is at or above the required tier."""
    stage = get("company.stage", "pre-seed", profile)
    try:
        return STAGE_ORDER.index(stage) >= STAGE_ORDER.index(required)
    except ValueError:
        return False


def sender_persona(profile: dict | None = None) -> dict:
    """First person in people: with sender_persona: true, or a company
    fallback. Returns {'name': ..., 'email': ...}."""
    p = profile if profile is not None else load()
    for person in p.get("people") or []:
        if person.get("sender_persona") and person.get("name"):
            return {"name": person["name"], "email": person.get("email", "")}
    return {"name": get("company.name", "Outreach", p), "email": ""}
