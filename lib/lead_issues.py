"""GitHub Issues as the human-facing CRM layer for manual sending.

`crm.provider: none` keeps the agent-facing record in leads/crm-local/*.jsonl.
Humans don't edit JSONL. So when `sending.provider` is "manual", every lead
whose touches were approved gets one GitHub issue (label `lead`) carrying
the paste-ready copy and a checkbox per touch. The human ticks a box when a
touch goes out and adds one `status:*` label when the outcome is known;
`lead-issue-sync.yml` runs `sync` on each edit and writes those actions back
into the local CRM (sequence_status, last_touch_*), sends/outcomes.jsonl
(what feedback-loop reads), and suppression/ (do-not-contact).

Confidentiality: these issues carry prospect names by design. They are the
scoped exception to rule 6 in CLAUDE.md, recorded in
docs/06-operational/decision-log/2026-09-20-instance-bootstrap.md, and they
depend on the repo staying private.

CLI:
    python3 lib/lead_issues.py create --files <queue files...> [--repo owner/name] [--dry-run]
    python3 lib/lead_issues.py sync --issue <number> [--repo owner/name]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crm  # noqa: E402
import manual_send  # noqa: E402
import suppression  # noqa: E402

LEAD_LABEL = "lead"
STATUS_PENDING = "status:pending"
STATUS_REPLIED = "status:replied"
STATUS_BOOKED = "status:booked"
STATUS_NO_RESPONSE = "status:no-response"
STATUS_DO_NOT_CONTACT = "status:do-not-contact"

LABELS = {
    LEAD_LABEL: ("0E8A16", "A lead in the manual-send pipeline — the human-facing CRM record"),
    STATUS_PENDING: ("FBCA04", "Touches drafted; nothing sent yet"),
    STATUS_REPLIED: ("1D76DB", "They replied — sequence paused, conversation is live"),
    STATUS_BOOKED: ("0E8A16", "Workshop or call booked"),
    STATUS_NO_RESPONSE: ("BFD4F2", "Sequence finished with no reply"),
    STATUS_DO_NOT_CONTACT: ("B60205", "They asked not to be contacted — suppressed, stop all touches"),
}

# Parses the line lib/manual_send.CHECKBOX_FMT renders.
CHECKBOX_RE = re.compile(
    r"^\s*- \[(?P<mark> |x|X)\] Touch (?P<n>\d+) — (?P<channel>email|linkedin)"
    r" — send on or after (?P<date>\d{4}-\d{2}-\d{2})",
    re.M,
)
TITLE_ID_RE = re.compile(r"\[(?P<lead_id>[^\[\]]+)\]\s*$")
EMAIL_RE = re.compile(r"\*\*Email:\*\*\s*(?P<email>[^\s*]+@[^\s*]+)")

OUTCOMES_PATH = Path(
    os.environ.get("OUTCOMES_PATH") or Path(__file__).resolve().parent.parent / "sends" / "outcomes.jsonl"
)
QUEUE_DIRS = (Path("sends/queue"), Path("sends/linkedin"))


# ---------------------------------------------------------------------------
# gh wrappers — the only I/O to GitHub, kept thin so tests can patch them
# ---------------------------------------------------------------------------

def _repo() -> str:
    return os.environ.get("GITHUB_REPOSITORY") or os.environ.get("REPO") or ""


def _gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return result.stdout


def ensure_labels(repo: str) -> None:
    for name, (color, desc) in LABELS.items():
        _gh(["label", "create", name, "--repo", repo, "--color", color, "--description", desc, "--force"])


def existing_issues(repo: str) -> dict[str, int]:
    """lead_id -> issue number for every `lead` issue, open or closed."""
    out = _gh([
        "issue", "list", "--repo", repo, "--label", LEAD_LABEL,
        "--state", "all", "--limit", "1000", "--json", "number,title",
    ])
    found: dict[str, int] = {}
    for item in json.loads(out or "[]"):
        lid = lead_id_from_title(item.get("title", ""))
        if lid and lid not in found:
            found[lid] = int(item["number"])
    return found


def create_issue(repo: str, title: str, body: str, labels: list[str]) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(body)
        body_path = f.name
    try:
        args = ["issue", "create", "--repo", repo, "--title", title, "--body-file", body_path]
        for label in labels:
            args += ["--label", label]
        return _gh(args).strip()
    finally:
        try:
            os.unlink(body_path)
        except OSError:
            pass


def fetch_issue(repo: str, number: int) -> dict:
    out = _gh(["issue", "view", str(number), "--repo", repo, "--json", "number,title,body,labels,state,author"])
    return json.loads(out)


def comment(repo: str, number: int, text: str) -> None:
    _gh(["issue", "comment", str(number), "--repo", repo, "--body", text])


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def lead_id_from_title(title: str) -> str | None:
    m = TITLE_ID_RE.search(title or "")
    return m.group("lead_id").strip() if m else None


def email_from_body(body: str) -> str | None:
    m = EMAIL_RE.search(body or "")
    if not m:
        return None
    email = m.group("email").strip().strip("`").lower()
    return email if email and email != "—" else None


def parse_checkboxes(body: str) -> list[dict]:
    boxes = []
    for m in CHECKBOX_RE.finditer(body or ""):
        boxes.append({
            "touch_number": int(m.group("n")),
            "channel": m.group("channel"),
            "checked": m.group("mark").lower() == "x",
            "send_after": m.group("date"),
        })
    return boxes


def label_names(issue: dict) -> set[str]:
    names = set()
    for label in issue.get("labels") or []:
        if isinstance(label, dict):
            names.add(label.get("name", ""))
        else:
            names.add(str(label))
    return {n for n in names if n}


def email_from_queue(lead_id: str, queue_dirs=QUEUE_DIRS) -> str | None:
    for d in queue_dirs:
        if not d.exists():
            continue
        for fp in d.glob("*.json"):
            try:
                item = json.loads(fp.read_text())
            except Exception:
                continue
            if item.get("lead_id") == lead_id and item.get("to"):
                return str(item["to"]).strip().lower()
    return None


# ---------------------------------------------------------------------------
# Outcomes ledger
# ---------------------------------------------------------------------------

def load_outcomes(path: Path = OUTCOMES_PATH) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def append_outcome(record: dict, path: Path = OUTCOMES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# create — one issue per lead with approved touches
# ---------------------------------------------------------------------------

def create_issues(files, *, repo: str, enriched_dir: Path, dry_run: bool = False, warn=print) -> list[dict]:
    touches = manual_send.load_touches(files)
    grouped = manual_send.group_by_lead(touches)
    if not grouped:
        print("No queue files — no issues to create.")
        return []
    contacts = manual_send.load_contacts(enriched_dir)
    existing = {} if dry_run else existing_issues(repo)
    if not dry_run:
        ensure_labels(repo)
    created = []
    for lead_id, lead_touches in grouped.items():
        if lead_id in existing:
            print(f"Issue already exists for [{lead_id}] (#{existing[lead_id]}) — skipped.")
            continue
        contact = manual_send.contact_for(lead_touches, contacts)
        title = manual_send.issue_title(lead_id, contact)
        body = manual_send.render_issue_body(lead_id, lead_touches, contact, warn=warn)
        if dry_run:
            print(f"[dry-run] would create: {title}")
            created.append({"lead_id": lead_id, "title": title, "url": None})
            continue
        url = create_issue(repo, title, body, [LEAD_LABEL, STATUS_PENDING])
        print(f"Created {url} for [{lead_id}]")
        created.append({"lead_id": lead_id, "title": title, "url": url})
    return created


# ---------------------------------------------------------------------------
# sync — human actions on an issue -> local CRM + outcomes ledger
# ---------------------------------------------------------------------------

def _ensure_contact(email: str, lead_id: str) -> dict:
    contact = crm.get_contact(email)
    if contact:
        return contact
    return crm.upsert_contact({"email": email, "sequence_status": "pending", "suppressed": False})


def _outcome(lead_id: str, email: str, event: str, actor: str, number: int, **extra) -> dict:
    rec = {"ts": _now_iso(), "lead_id": lead_id, "email": email, "event": event,
           "source": "issue-sync", "actor": actor, "issue_number": number}
    rec.update(extra)
    return rec


def _record_touches(body: str, ctx: dict, seen_touches: set, outcomes_path: Path) -> list[tuple]:
    """Checkbox ticks -> touch_sent outcomes + last_touch_* on the contact."""
    recorded: list[tuple] = []
    max_touch = None
    for box in parse_checkboxes(body):
        key = (box["touch_number"], box["channel"])
        if not box["checked"] or key in seen_touches:
            continue
        append_outcome(_outcome(ctx["lead_id"], ctx["email"], "touch_sent", ctx["actor"], ctx["number"],
                                touch_number=box["touch_number"], channel=box["channel"]), outcomes_path)
        seen_touches.add(key)
        recorded.append(key)
        max_touch = box["touch_number"] if max_touch is None else max(max_touch, box["touch_number"])
        crm.log_interaction(
            ctx["contact_id"],
            f"Touch {box['touch_number']} ({box['channel']}) sent by hand on {ctx['today']}; "
            f"recorded from issue #{ctx['number']}.",
        )
    if max_touch is not None:
        crm.set_field(ctx["contact_id"], "last_touch_date", ctx["today"])
        crm.set_field(ctx["contact_id"], "last_touch_number", max_touch)
        touch_one_sent = any(k[0] == 1 for k in seen_touches)
        if touch_one_sent and ctx["contact"].get("sequence_status") in (None, "", "pending"):
            crm.set_field(ctx["contact_id"], "sequence_status", "enrolled")
            crm.set_field(ctx["contact_id"], "sequence_enrolled_date", ctx["today"])
            ctx["contact"]["sequence_status"] = "enrolled"
    return recorded


# label -> (sequence_status, reply_received or None, outcome event)
_STATUS_EFFECTS = {
    STATUS_DO_NOT_CONTACT: ("rejected", None, "do_not_contact"),
    STATUS_REPLIED: ("paused", True, "replied"),
    STATUS_BOOKED: ("completed", True, "booked"),
    STATUS_NO_RESPONSE: ("completed", None, "no_response"),
}
_STATUS_PRECEDENCE = (STATUS_DO_NOT_CONTACT, STATUS_REPLIED, STATUS_BOOKED, STATUS_NO_RESPONSE)

DO_NOT_CONTACT_COMMENT = (
    "Sequence stopped — this contact asked not to be contacted. The address is now on the "
    "suppression list; do not send the remaining touches."
)


def _apply_status(issue: dict, ctx: dict, seen_events: set, outcomes_path: Path, repo: str, comment_fn) -> str | None:
    """Status labels -> sequence state + one outcome line each (deduped)."""
    labels = label_names(issue)
    label = next((lbl for lbl in _STATUS_PRECEDENCE if lbl in labels), None)
    if label is None:
        if (issue.get("state") or "").upper() == "CLOSED" and "note" not in seen_events:
            append_outcome(_outcome(ctx["lead_id"], ctx["email"], "note", ctx["actor"], ctx["number"],
                                    note="issue closed without a status label"), outcomes_path)
            return "closed_without_status"
        return None
    status, reply_received, event = _STATUS_EFFECTS[label]
    crm.set_field(ctx["contact_id"], "sequence_status", status)
    if reply_received is not None:
        crm.set_field(ctx["contact_id"], "reply_received", reply_received)
    if label == STATUS_DO_NOT_CONTACT:
        crm.set_field(ctx["contact_id"], "suppressed", True)
        if not suppression.check(ctx["email"]):
            suppression.add(ctx["email"], "unsubscribed", "lead-issue-sync")
    if event not in seen_events:
        append_outcome(_outcome(ctx["lead_id"], ctx["email"], event, ctx["actor"], ctx["number"]), outcomes_path)
        if label == STATUS_DO_NOT_CONTACT and comment_fn and repo:
            comment_fn(repo, ctx["number"], DO_NOT_CONTACT_COMMENT)
    return event


def sync_issue(
    issue: dict,
    *,
    today: str,
    outcomes_path: Path = OUTCOMES_PATH,
    queue_dirs=QUEUE_DIRS,
    repo: str = "",
    comment_fn=None,
) -> dict:
    """Read one `lead` issue and write its human actions into the local CRM,
    sends/outcomes.jsonl and (for do-not-contact) suppression/. Idempotent:
    a tick or label already recorded produces no second outcome line.
    `comment_fn(repo, number, text)` posts the do-not-contact notice."""
    number = int(issue.get("number", 0))
    body = issue.get("body") or ""
    author = issue.get("author")
    actor = (author.get("login") if isinstance(author, dict) else "") or ""
    lead_id = lead_id_from_title(issue.get("title", ""))
    summary = {"issue": number, "lead_id": lead_id, "touches_recorded": [], "status": None, "skipped": None}
    if not lead_id:
        summary["skipped"] = "no [lead_id] in title"
        return summary

    email = email_from_body(body) or email_from_queue(lead_id, queue_dirs)
    if not email:
        summary["skipped"] = "no email found in issue body or queue files"
        return summary

    prior = [r for r in load_outcomes(outcomes_path) if r.get("lead_id") == lead_id]
    seen_touches = {(r.get("touch_number"), r.get("channel")) for r in prior if r.get("event") == "touch_sent"}
    seen_events = {r.get("event") for r in prior}

    contact = _ensure_contact(email, lead_id)
    ctx = {
        "lead_id": lead_id, "email": email, "actor": actor, "number": number, "today": today,
        "contact": contact, "contact_id": contact.get("id") or email.lower(),
    }
    summary["touches_recorded"] = _record_touches(body, ctx, seen_touches, outcomes_path)
    summary["status"] = _apply_status(issue, ctx, seen_events, outcomes_path, repo, comment_fn)
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    cr = sub.add_parser("create", help="Open one `lead` issue per lead in the given queue files")
    cr.add_argument("--files", nargs="*", default=[])
    cr.add_argument("--repo", default=_repo())
    cr.add_argument("--enriched-dir", default="leads/enriched")
    cr.add_argument("--dry-run", action="store_true")

    sy = sub.add_parser("sync", help="Write an issue's checkbox ticks and status labels into the local CRM")
    sy.add_argument("--issue", type=int, required=True)
    sy.add_argument("--repo", default=_repo())
    sy.add_argument("--today", default=date.today().isoformat())

    args = parser.parse_args(argv)
    if args.cmd == "create":
        files = [f for f in args.files if f]
        if not files:
            print("No queue files — no issues to create.")
            return 0
        if not args.repo and not args.dry_run:
            print("::error::no repo given (set GITHUB_REPOSITORY or --repo)")
            return 1
        created = create_issues(files, repo=args.repo, enriched_dir=Path(args.enriched_dir), dry_run=args.dry_run)
        print(f"{len(created)} issue(s) {'would be ' if args.dry_run else ''}created.")
        return 0

    if args.cmd == "sync":
        if not args.repo:
            print("::error::no repo given (set GITHUB_REPOSITORY or --repo)")
            return 1
        issue = fetch_issue(args.repo, args.issue)
        if LEAD_LABEL not in label_names(issue):
            print(f"Issue #{args.issue} is not labelled `{LEAD_LABEL}` — nothing to sync.")
            return 0
        summary = sync_issue(issue, today=args.today, repo=args.repo, comment_fn=comment)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
