"""Manual-send packet renderer.

When `sending.provider` is "manual", nothing is emailed by CI. The
sequence-enrollment agent still drafts every touch and the copy-evaluator
still gates them, and merging the approval PR is still the approval. What
changes is what happens after merge: instead of smtp-send processing
`sends/queue/`, `manual-send-packet.yml` runs this module to compile the
approved queue files into one paste-ready markdown packet
(`sends/manual/YYYY-MM-DD-send-packet.md`) and, via lib/lead_issues.py, one
GitHub issue per lead with a checkbox per touch.

Queue files stay in place after compilation: the sequence-enrollment agent's
"already drafted" check depends on them, and smtp-send is a no-op in manual
mode so nothing will ever pick them up.

Body text is passed through lib/format_body.unwrap_body so a body that was
hard-wrapped at draft time pastes as one line per paragraph. Bodies sit in
fenced code blocks so GitHub renders a copy button on each one.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import format_body  # noqa: E402

REQUIRED_TOUCH_KEYS = ("lead_id", "touch_number", "channel", "scheduled_date", "to", "subject", "body", "from_name")

# The exact checkbox shape lib/lead_issues.py parses back. Keep them in sync.
CHECKBOX_FMT = "- [ ] Touch {n} — {channel} — send on or after {date}"


def load_touches(paths) -> list[dict]:
    """Load queue files; each must carry every REQUIRED_TOUCH_KEYS entry."""
    touches: list[dict] = []
    for raw in paths:
        p = Path(raw)
        if not p.exists() or p.suffix != ".json":
            continue
        try:
            item = json.loads(p.read_text())
        except Exception as e:
            raise ValueError(f"{p}: unparseable JSON — {e}") from e
        missing = [k for k in REQUIRED_TOUCH_KEYS if k not in item]
        if missing:
            raise ValueError(f"{p}: missing required keys {missing}")
        item = dict(item)
        item["_path"] = str(p)
        touches.append(item)
    return touches


def group_by_lead(touches: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for t in touches:
        grouped.setdefault(t["lead_id"], []).append(t)
    for lead_id in grouped:
        grouped[lead_id].sort(key=lambda t: (int(t.get("touch_number", 0)), t.get("scheduled_date", "")))
    return grouped


def load_contacts(enriched_dir: Path) -> dict[str, dict]:
    """email (lower) -> enriched lead record. Later files win, so a
    re-enriched contact carries its newest fields."""
    contacts: dict[str, dict] = {}
    if not enriched_dir.exists():
        return contacts
    for fp in sorted(enriched_dir.glob("*.json")):
        try:
            records = json.loads(fp.read_text())
        except Exception:
            continue
        if not isinstance(records, list):
            records = [records]
        for r in records:
            email = (r.get("email") or "").strip().lower()
            if email:
                contacts[email] = r
    return contacts


def contact_for(touches: list[dict], contacts: dict[str, dict]) -> dict:
    """The enriched record for a lead's touches, or a minimal stand-in."""
    for t in touches:
        rec = contacts.get((t.get("to") or "").strip().lower())
        if rec:
            return rec
    first = touches[0] if touches else {}
    return {"email": first.get("to", ""), "contact_name": "", "company_name": "", "contact_title": ""}


def issue_title(lead_id: str, contact: dict) -> str:
    name = contact.get("contact_name") or "Unknown contact"
    company = contact.get("company_name") or "unknown company"
    return f"Lead: {name} — {company} [{lead_id}]"


def _signal_line(contact: dict) -> str:
    if contact.get("signal"):
        return str(contact["signal"])
    hs = contact.get("hiring_signal")
    if isinstance(hs, dict) and hs.get("role"):
        return f"hiring: {hs['role']} ({hs.get('date', '')})"
    pains = contact.get("pain_points")
    if isinstance(pains, list) and pains and isinstance(pains[0], dict) and pains[0].get("quote"):
        return f"pain: \"{pains[0]['quote']}\""
    return ""


def render_contact_card(lead_id: str, contact: dict) -> str:
    lines = [
        f"**Name:** {contact.get('contact_name') or '—'}",
        f"**Title:** {contact.get('contact_title') or '—'}",
        f"**Company:** {contact.get('company_name') or '—'}",
        f"**Email:** {contact.get('email') or '—'}",
        f"**LinkedIn:** {contact.get('linkedin_url') or '—'}",
    ]
    location = contact.get("contact_location") or contact.get("company_hq_location")
    if location or contact.get("metro_match"):
        lines.append(f"**Location:** {location or '—'} (metro match: {contact.get('metro_match') or 'unknown'})")
    if contact.get("icp_segment"):
        lines.append(f"**Segment:** {contact['icp_segment']}")
    signal = _signal_line(contact)
    if signal:
        lines.append(f"**Why now:** {signal}")
    if contact.get("icp_rationale"):
        lines.append(f"**Why them:** {contact['icp_rationale']}")
    lines.append(f"**Lead id:** `{lead_id}`")
    return "\n".join(lines)


def render_touch_block(touch: dict, contact: dict, warn=print) -> str:
    body = touch.get("body") or ""
    unwrapped = format_body.unwrap_body(body)
    if unwrapped != body:
        warn(f"::warning::{touch.get('_path', touch.get('lead_id'))}: body was hard-wrapped; unwrapped for pasting")
    n = touch.get("touch_number")
    channel = touch.get("channel") or "email"
    header = CHECKBOX_FMT.format(n=n, channel=channel, date=touch.get("scheduled_date", ""))
    lines = [header]
    if channel == "linkedin":
        profile = contact.get("linkedin_url") or "profile URL not on record — find them on LinkedIn by name and company"
        lines.append(f"  **Send from:** {touch.get('from_name', '')}'s own LinkedIn profile")
        lines.append(f"  **To:** {profile}")
        lines.append("  **Connection note (300 characters max):**")
    else:
        lines.append(f"  **From:** {touch.get('from_name', '')} (your own mailbox)")
        lines.append(f"  **To:** {touch.get('to', '')}")
        lines.append(f"  **Subject:** {touch.get('subject', '')}")
    lines.append("")
    lines.append("  ```text")
    lines.extend("  " + line if line else "" for line in unwrapped.split("\n"))
    lines.append("  ```")
    return "\n".join(lines)


HOW_TO_SEND = (
    "**How to work this lead:** send each touch on or after its date from your own mailbox or LinkedIn "
    "profile, paste the copy exactly (the copy button on each block copies it), then tick the box. When "
    "they answer, add a status label: `status:replied`, `status:booked`, `status:no-response`, or "
    "`status:do-not-contact` (that last one stops every remaining touch and suppresses the address). "
    "A workflow reads your ticks and labels back into the local CRM — you never have to edit a data file."
)


def render_issue_body(lead_id: str, touches: list[dict], contact: dict, warn=print) -> str:
    parts = [HOW_TO_SEND, "", "## Contact", render_contact_card(lead_id, contact), "", "## Touches"]
    for t in touches:
        parts.append(render_touch_block(t, contact, warn=warn))
        parts.append("")
    parts.append("## Outcome")
    parts.append(
        "Add one `status:*` label when you know it. Notes about the conversation go in comments — "
        "they stay here, in this private repo."
    )
    return "\n".join(parts).rstrip() + "\n"


def render_packet(grouped: dict[str, list[dict]], contacts: dict[str, dict], today: str, warn=print) -> str:
    parts = [
        f"# Send packet — {today}",
        "",
        f"{len(grouped)} lead(s), {sum(len(v) for v in grouped.values())} touch(es). Nothing here is sent by "
        "the system; every block below is for a human to paste from their own mailbox or LinkedIn profile. "
        "Each lead also has a GitHub issue (label `lead`) with the same copy and a checkbox per touch — tick "
        "there so the CRM knows what went out.",
        "",
        HOW_TO_SEND,
        "",
    ]
    for lead_id, touches in grouped.items():
        contact = contact_for(touches, contacts)
        name = contact.get("contact_name") or "Unknown contact"
        company = contact.get("company_name") or "unknown company"
        parts.append(f"## {name} — {company} [{lead_id}]")
        parts.append("")
        parts.append(render_contact_card(lead_id, contact))
        parts.append("")
        for t in touches:
            parts.append(render_touch_block(t, contact, warn=warn))
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def build_packet(files, *, enriched_dir: Path, today: str, warn=print) -> tuple[str, dict[str, list[dict]]]:
    touches = load_touches(files)
    grouped = group_by_lead(touches)
    contacts = load_contacts(enriched_dir)
    return render_packet(grouped, contacts, today, warn=warn), grouped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    pk = sub.add_parser("packet", help="Render a send packet from approved queue files")
    pk.add_argument("--files", nargs="*", default=[], help="sends/queue and sends/linkedin JSON files")
    pk.add_argument("--out", required=True, help="Path of the markdown packet to write")
    pk.add_argument("--enriched-dir", default="leads/enriched")
    pk.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args(argv)

    if args.cmd == "packet":
        files = [f for f in args.files if f]
        if not files:
            print("No queue files to compile — nothing written.")
            return 0
        packet, grouped = build_packet(files, enriched_dir=Path(args.enriched_dir), today=args.today)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(packet)
        print(f"Wrote {out}: {len(grouped)} lead(s), {sum(len(v) for v in grouped.values())} touch(es).")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
