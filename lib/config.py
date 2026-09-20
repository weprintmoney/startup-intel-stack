"""Tiny helper that loads company-profile.yaml — the single source of
company-specific parameters for every agent and library in this repo.

Usage:
    import config
    profile = config.load()
    cap = config.get("sending.daily_cap", 100)
    if not config.mode_at_least("find-leads"):
        sys.exit(0)
"""

import os
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).parent.parent / "company-profile.yaml"

# How much of the system is switched on, lowest to highest. Each mode
# includes everything below it:
#
#   docs-only      research and writing only — market/competitor signals,
#                  positioning, ICP, brand voice, content ops. Touches no
#                  contact data.
#   find-leads     + the lead pipeline: crawl, dedup, pre-filter, enrich,
#                  qualify against the rubric. Produces a scored lead list.
#                  Writes no outreach.
#   find-and-draft + drafts outreach for qualified leads and opens an
#                   approval PR, + sending of what you approve there.
#
# The older fundraising-stage names are accepted as aliases so existing
# instances keep working; new instances should use the mode names, which
# say what they actually do.
MODE_ORDER = ["docs-only", "find-leads", "find-and-draft"]

MODE_ALIASES = {
    "pre-seed": "docs-only",
    "seed": "find-leads",
    "series-a": "find-and-draft",
}


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


def normalize_mode(value: str | None) -> str | None:
    """Map a configured mode (or a legacy fundraising-stage alias) onto a
    canonical MODE_ORDER value. Returns None for anything unrecognized —
    callers should say so out loud rather than silently picking a default."""
    if not value:
        return None
    v = str(value).strip().lower()
    v = MODE_ALIASES.get(v, v)
    return v if v in MODE_ORDER else None


def mode(profile: dict | None = None) -> str:
    """The instance's configured mode, canonicalized.

    Reads company.mode, falling back to the legacy company.stage. An
    unrecognized value falls back to the most restrictive mode and prints a
    warning — a typo here would otherwise switch the whole pipeline off with
    no visible reason."""
    raw = get("company.mode", None, profile) or get("company.stage", None, profile)
    resolved = normalize_mode(raw)
    if resolved is None:
        if raw:
            print(
                f"::warning::company.mode '{raw}' is not recognized — expected one of "
                f"{', '.join(MODE_ORDER)}. Falling back to '{MODE_ORDER[0]}'."
            )
        return MODE_ORDER[0]
    return resolved


def mode_at_least(required: str, profile: dict | None = None) -> bool:
    """True if the instance's mode is at or above `required`."""
    required_mode = normalize_mode(required)
    if required_mode is None:
        raise ValueError(f"Unknown mode {required!r} — expected one of {MODE_ORDER}")
    return MODE_ORDER.index(mode(profile)) >= MODE_ORDER.index(required_mode)


def stage_at_least(required: str, profile: dict | None = None) -> bool:
    """Deprecated alias for mode_at_least(), kept so existing instances and
    agent prompts that say "stage" keep working."""
    return mode_at_least(required, profile)


MANUAL_PROVIDER = "manual"


def sending_provider(profile: dict | None = None) -> str:
    """`sending.provider`, lower-cased, defaulting to resend. The value
    "manual" means the system drafts and a human sends by hand — see
    lib/manual_send.py and lib/lead_issues.py."""
    return str(get("sending.provider", "resend", profile) or "resend").strip().lower()


def is_manual_sending(profile: dict | None = None) -> bool:
    """True when nothing may be emailed by CI: drafts become a copy-paste
    packet and per-lead GitHub issues instead of a send queue."""
    return sending_provider(profile) == MANUAL_PROVIDER


def sender_persona(profile: dict | None = None) -> dict:
    """First person in people: with sender_persona: true, or a company
    fallback. Returns {'name': ..., 'email': ...}."""
    p = profile if profile is not None else load()
    for person in p.get("people") or []:
        if person.get("sender_persona") and person.get("name"):
            return {"name": person["name"], "email": person.get("email", "")}
    return {"name": get("company.name", "Outreach", p), "email": ""}
