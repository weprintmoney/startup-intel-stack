#!/usr/bin/env python3
"""One status card per (ticket, implementation repo): the bot's single comment on a ticket.

Before this, every stage narrated its own state as a fresh comment — claimed,
spec PR opened, attempt N failed, retrying, abandoned — and a clean run left
6–8 bot comments on a ticket; a retry loop left 22.
Now the pipeline posts ONE comment at claim time and rewrites it in place as
the claim moves claimed → spec → implement → PR → merged, with links, the
retry count, and a run-URL history so nothing the old comments said is lost.
New comments are reserved for a human being asked something (the drafter's
@-mention questions, an intent note, a blocker quote) and are posted from an
outbox by the workflow, never by the model — see `post-outbox`.

The comment carries a marker the pipeline finds it by, and a JSON payload the
pipeline reads back; humans see the table between them. Same idempotent-block
idea as `round-history.py` (PR body) and `dependabot-triage.py` (PR comment):

    <!-- agent-ops:status-card issue=1468 impl_repo=<YOUR_ORG>/example-app-sdk-py -->
    ...table, latest event, collapsed history...
    <!-- agent-ops:status-card:data {...} -->

`state/queue.json` stays the state of record; the card is a projection of it
and is never read to make a pipeline decision. Every API failure here is a
`::warning::` and exit 0 — a cosmetic write must never fail a stage.

Subcommands (all need `gh` authenticated with issues:write on --repo):
  upsert       --repo R --issue N --impl-repo R2 --event SLUG
               [--status <queue status> | -] [--note TEXT] [--run-url URL]
               [--set key=value ...]
               Create the card if absent, else rewrite it. `--status -` keeps
               the recorded status (history-only event). Settable keys:
               branch, spec_pr, spec_path, pr_url, claim_verification,
               abandoned_reason, merge_sha, retry_count, spec_fast_path,
               clarify_reason, blocked_by.
  post-outbox  --repo R --issue N --impl-repo R2 --dir DIR --result RESULT
               --people named-people.yaml [--run-url URL]
               Post the drafter's human-facing comments from DIR (see OUTBOX
               below), then record one history line per posted comment.
  render       --payload FILE     print the rendered card (tests, debugging)

OUTBOX — the only way a model node gets a new comment onto a ticket. The
drafter's ticket-repo token is read-only; it writes files, the workflow posts
them, and the rules are enforced here, not in the prompt:
  question-<handle>.md   one per person; handle must be in named-people.yaml
                         and the body must @-mention that handle
  intent-note.md         only with RESULT FAST_PATH
  clarify.md             only with RESULT CLARIFY_NEEDED
  blocker.md             only with RESULT GROOMING_BLOCKER | DEPENDENCY_BLOCKED | UNFIT
Anything else is dropped with a warning. An @handle outside named-people.yaml
is defanged to plain text. A body identical to an existing comment on the
ticket is skipped (a retry run re-asking the same question). At most
MAX_OUTBOX posts per run.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MARKER_RE = re.compile(r"<!-- agent-ops:status-card issue=(\d+) impl_repo=(\S+) -->")
DATA_RE = re.compile(r"<!-- agent-ops:status-card:data (.*?) -->", re.S)

STATUSES = ("claimed", "spec-pending", "spec-clarify-pending", "spec-approved",
            "implementing", "pr-open", "merged", "abandoned")
# Stage each non-terminal status belongs to; abandoned reports the stage it fell from.
STAGE_OF = {"claimed": 1, "spec-pending": 1, "spec-clarify-pending": 1, "spec-approved": 2,
            "implementing": 2, "pr-open": 3, "merged": 4}
STAGE_NAMES = ("Claim", "Spec", "Implement", "PR", "Merged")
SETTABLE = {"branch": str, "spec_pr": str, "spec_path": str, "pr_url": str, "claim_verification": str,
            "abandoned_reason": str, "merge_sha": str, "retry_count": int, "spec_fast_path": bool,
            "clarify_reason": str, "blocked_by": str}
MAX_RETRIES = 3          # spec-draft.yml MAX_RETRIES — shown as n/3 on the card
HISTORY_KEEP = 60        # newest events kept in the payload (comment size cap is 64 KiB)
MAX_OUTBOX = 10
MAX_COMMENT_CHARS = 20000
HANDLE_RE = re.compile(r"(?<![\w/.-])@([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)")

DONE, ACTIVE, TODO, FAILED, PARKED = "✅", "🟡", "⬜", "❌", "⏸️"


class GhError(RuntimeError):
    pass


def gh(*args: str) -> str:
    """Run `gh` and return stdout. Monkeypatched in tests."""
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise GhError((p.stderr or p.stdout).strip() or f"gh {' '.join(args)} failed ({p.returncode})")
    return p.stdout


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ payload ---

def new_payload(issue: int, impl_repo: str) -> dict:
    return {"v": 1, "issue": issue, "impl_repo": impl_repo, "status": "claimed", "abandoned_from": "",
            "branch": "", "spec_pr": "", "spec_path": "", "pr_url": "", "claim_verification": "",
            "abandoned_reason": "", "merge_sha": "", "retry_count": 0, "spec_fast_path": False,
            "clarify_reason": "", "blocked_by": "", "updated_at": "", "history": []}


def read_payload(body: str, issue: int, impl_repo: str) -> dict:
    base = new_payload(issue, impl_repo)
    m = DATA_RE.search(body or "")
    if not m:
        return base
    try:
        data = json.loads(m.group(1).replace("\\u003e", ">"))
    except json.JSONDecodeError as e:
        print(f"::warning::status card data block is not valid JSON ({e}); starting a fresh payload")
        return base
    base.update({k: v for k, v in data.items() if k in base})
    base["history"] = [h for h in base["history"] if isinstance(h, dict)]
    return base


def coerce(key: str, raw: str):
    if key not in SETTABLE:
        raise SystemExit(f"--set {key}: not a card field (allowed: {', '.join(sorted(SETTABLE))})")
    t = SETTABLE[key]
    if t is bool:
        return raw.strip().lower() in ("1", "true", "yes")
    if t is int:
        try:
            return int(raw)
        except ValueError as e:
            raise SystemExit(f"--set {key}: expected an integer, got {raw!r}") from e
    return raw


def apply(payload: dict, event: str, status: str | None, note: str, run_url: str,
          sets: dict | None = None, at: str | None = None) -> dict:
    """Pure state transition: record one event, move status, apply field sets."""
    at = at or now_iso()
    p = dict(payload)
    p["history"] = list(payload.get("history", []))
    for k, v in (sets or {}).items():
        p[k] = v
    if status and status != "-":
        if status not in STATUSES:
            raise SystemExit(f"--status {status}: not a queue status ({', '.join(STATUSES)})")
        if status == "abandoned" and p["status"] != "abandoned":
            p["abandoned_from"] = p["status"]
        if status != "abandoned":
            p["abandoned_from"] = ""
            if p["status"] == "abandoned":
                # Re-claim after an abandon: the terminal facts belong to the previous
                # lifecycle, the history keeps them; the live fields start over.
                for k in ("spec_pr", "spec_path", "pr_url", "claim_verification", "abandoned_reason",
                          "merge_sha", "clarify_reason", "blocked_by"):
                    p[k] = "" if k not in (sets or {}) else p[k]
                p["retry_count"] = (sets or {}).get("retry_count", 0)
                p["spec_fast_path"] = (sets or {}).get("spec_fast_path", False)
        p["status"] = status
    p["history"].append({"at": at, "event": event, "note": note or "", "run_url": run_url or ""})
    p["history"] = p["history"][-HISTORY_KEEP:]
    p["updated_at"] = at
    return p


# ------------------------------------------------------------------- render ---

def _short(iso: str) -> str:
    return iso.replace("T", " ")[:16] + "Z" if iso else "—"


def _link(url: str, label: str | None = None) -> str:
    if not url:
        return ""
    if label is None:
        m = re.search(r"github\.com/[^/]+/([^/]+)/pull/(\d+)$", url)
        label = f"{m.group(1)}#{m.group(2)}" if m else "link"
    return f"[{label}]({url})"


def _run(url: str) -> str:
    return _link(url, "run") if url else ""


def _first_event(p: dict, *events: str) -> dict | None:
    return next((h for h in p["history"] if h.get("event") in events), None)


def _last_event(p: dict, *events: str) -> dict | None:
    return next((h for h in reversed(p["history"]) if h.get("event") in events), None)


def _spec_row(p: dict, reached: int, stage: int) -> tuple[str, str, str]:
    status = p["status"]
    links = _link(p["spec_pr"]) if p["spec_pr"] else ""
    if p["claim_verification"]:
        links = " · ".join(x for x in (links, f"claims `{p['claim_verification']}`") if x)
    if reached > stage:
        how = "fast path — no spec needed" if p["spec_fast_path"] else "approved (spec PR merged)"
        return DONE, how, links
    if status == "spec-pending":
        return ACTIVE, "spec PR open — merging it is the approval", links
    if status == "spec-clarify-pending":
        why = f" — {p['clarify_reason']}" if p["clarify_reason"] else ""
        return PARKED, f"parked on one clarifying question{why}", links
    if p["retry_count"]:
        n = p["retry_count"]
        return ACTIVE, f"drafting — attempt {n + 1}, {n}/{MAX_RETRIES} retries used", links
    return ACTIVE, "queued for spec draft", links


def _implement_row(p: dict, reached: int, stage: int) -> tuple[str, str, str]:
    ev = _last_event(p, "implementing")
    run = _run(ev["run_url"]) if ev else ""
    if reached > stage:
        return DONE, "implemented — PR opened", run
    if p["status"] == "implementing":
        return ACTIVE, "implementing (plan → code → two fresh-context reviews)", run
    if p["status"] == "spec-approved":
        return ACTIVE, "approved — implement dispatched", run
    return TODO, "", ""


def _pr_row(p: dict, reached: int, stage: int) -> tuple[str, str, str]:
    link = _link(p["pr_url"]) if p["pr_url"] else ""
    if reached > stage:
        return DONE, "merged", link
    if p["status"] == "pr-open":
        return ACTIVE, "open — awaiting human review (judge and revise rounds live on the PR)", link
    return TODO, "", ""


def _merged_row(p: dict, reached: int, stage: int) -> tuple[str, str, str]:
    if p["status"] == "merged":
        sha = f"`{p['merge_sha'][:7]}`" if p["merge_sha"] else ""
        return DONE, "merged — claim closed", sha
    return TODO, "", ""


def stage_rows(p: dict) -> list[tuple[str, str, str, str]]:
    """(stage, mark, state, links) per row. Abandoned marks the stage it fell from."""
    status = p["status"]
    live = p["abandoned_from"] if status == "abandoned" else status
    reached = STAGE_OF.get(live, 1)
    claimed = _first_event(p, "claimed")
    branch = f"branch `{p['branch']}`" if p["branch"] else ""
    rows = [("Claim", DONE, f"claimed {_short(claimed['at']) if claimed else ''}".strip(),
             " · ".join(x for x in (branch, _run(claimed["run_url"]) if claimed else "") if x))]
    for stage, fn in ((1, _spec_row), (2, _implement_row), (3, _pr_row), (4, _merged_row)):
        mark, state, links = fn(p, reached, stage)
        if status == "abandoned" and stage == reached:
            mark = FAILED
            state = f"abandoned — {p['abandoned_reason'] or 'no reason recorded'}"
        rows.append((STAGE_NAMES[stage], mark, state, links))
    return rows


def render(p: dict) -> str:
    badge = f"`{p['status']}`"
    if p["status"] == "abandoned" and p["abandoned_from"]:
        badge += f" (from `{p['abandoned_from']}`)"
    lines = [f"<!-- agent-ops:status-card issue={p['issue']} impl_repo={p['impl_repo']} -->",
             f"**agent-ops** · `{p['impl_repo']}` · {badge}", "",
             "| Stage | | State | Links |", "|---|---|---|---|"]
    for stage, mark, state, links in stage_rows(p):
        lines.append(f"| {stage} | {mark} | {state} | {links} |")
    hist = p["history"]
    if hist:
        last = hist[-1]
        tail = f" · {_run(last['run_url'])}" if last.get("run_url") else ""
        lines += ["", f"**Latest** — {_short(last['at'])} · {last['event']}"
                  + (f": {last['note']}" if last.get("note") else "") + tail]
        lines += ["", f"<details><summary>History · {len(hist)} event{'s' if len(hist) != 1 else ''}</summary>", "",
                  "| When (UTC) | Event | Note | Run |", "|---|---|---|---|"]
        for h in hist:
            note = (h.get("note") or "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {_short(h['at'])} | {h['event']} | {note} | {_run(h.get('run_url', ''))} |")
        lines += ["", "</details>"]
    lines += ["", "<sub>One card per (ticket, implementation repo), rewritten in place by agent-ops; "
              "questions for humans are separate @-mention comments. State of record: "
              "<code>state/queue.json</code>.</sub>"]
    # '>' escaped so the JSON can never terminate the HTML comment early (round-history.py).
    data = json.dumps(p, separators=(",", ":"), sort_keys=True, ensure_ascii=False).replace(">", "\\u003e")
    lines.append(f"<!-- agent-ops:status-card:data {data} -->")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- comments ---

def list_comments(repo: str, issue: int) -> list[dict]:
    out = gh("api", "--paginate", f"repos/{repo}/issues/{issue}/comments", "--jq", ".[] | {id, body}")
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def find_card(comments: list[dict], issue: int, impl_repo: str) -> dict | None:
    for c in comments:
        m = MARKER_RE.search(c.get("body") or "")
        if m and int(m.group(1)) == issue and m.group(2) == impl_repo:
            return c
    return None


def write_comment(repo: str, issue: int, body: str, existing_id: int | None) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(body)
        path = f.name
    try:
        if existing_id:
            gh("api", "-X", "PATCH", f"repos/{repo}/issues/comments/{existing_id}", "-F", f"body=@{path}")
        else:
            gh("api", "-X", "POST", f"repos/{repo}/issues/{issue}/comments", "-F", f"body=@{path}")
    finally:
        Path(path).unlink(missing_ok=True)


def upsert(repo: str, issue: int, impl_repo: str, events: list[dict], comments: list[dict] | None = None) -> dict:
    """Apply events to the card for (issue, impl_repo), creating it if needed. Never raises on gh errors."""
    try:
        comments = list_comments(repo, issue) if comments is None else comments
    except GhError as e:
        print(f"::warning::status card: cannot list comments on {repo}#{issue} ({e}) — card not updated")
        return {}
    card = find_card(comments, issue, impl_repo)
    payload = read_payload(card["body"] if card else "", issue, impl_repo)
    for ev in events:
        payload = apply(payload, ev["event"], ev.get("status"), ev.get("note", ""), ev.get("run_url", ""),
                        ev.get("sets"), ev.get("at"))
    try:
        write_comment(repo, issue, render(payload), card["id"] if card else None)
    except GhError as e:
        print(f"::warning::status card: could not {'update' if card else 'create'} the card on {repo}#{issue} ({e})")
        return payload
    print(f"status card {'updated' if card else 'created'} on {repo}#{issue} ({impl_repo}): "
          f"{payload['status']} · {events[-1]['event']}")
    return payload


# ------------------------------------------------------------------- outbox ---

def load_people(path: str) -> set[str]:
    """Handles from named-people.yaml — a flat grep, no YAML dependency (same as the drafter's closed list)."""
    text = Path(path).read_text(encoding="utf-8") if path and Path(path).is_file() else ""
    return {m.group(1).lower() for m in re.finditer(r"^\s*-\s*handle:\s*([A-Za-z0-9-]+)", text, re.M)}


def defang_handles(body: str, people: set[str]) -> tuple[str, list[str]]:
    """Keep @mentions for handles in the closed list; turn every other @handle into plain text."""
    dropped: list[str] = []

    def sub(m: re.Match) -> str:
        h = m.group(1)
        if h.lower() in people:
            return m.group(0)
        dropped.append(h)
        return h
    return HANDLE_RE.sub(sub, body), dropped


def classify(name: str, result: str, people: set[str]) -> tuple[str, str] | None:
    """(kind, handle-or-'') if this outbox filename is allowed under RESULT, else None."""
    m = re.fullmatch(r"question-([A-Za-z0-9-]+)\.md", name)
    if m:
        return ("question", m.group(1)) if m.group(1).lower() in people else None
    allowed = {"intent-note.md": {"FAST_PATH"}, "clarify.md": {"CLARIFY_NEEDED"},
               "blocker.md": {"GROOMING_BLOCKER", "DEPENDENCY_BLOCKED", "UNFIT"}}
    if name in allowed and result in allowed[name]:
        return (name[:-3], "")
    return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def select_outbox(outbox: Path, result: str, people: set[str], existing_bodies: list[str]) -> list[dict]:
    """Decide what gets posted. Pure: returns [{name, kind, handle, body}] in filename order."""
    chosen: list[dict] = []
    seen = {_norm(b) for b in existing_bodies}
    for f in sorted(outbox.glob("*.md")) if outbox.is_dir() else []:
        kind = classify(f.name, result, people)
        if not kind:
            print(f"::warning::outbox: dropped {f.name} — not an allowed comment under RESULT {result or '(none)'}")
            continue
        body = f.read_text(encoding="utf-8").strip()
        if not body:
            print(f"::warning::outbox: dropped {f.name} — empty")
            continue
        body, dropped = defang_handles(body, people)
        if dropped:
            print(f"::warning::outbox: {f.name} mentioned handles outside named-people.yaml, "
                  f"defanged: {', '.join(dropped)}")
        if kind[0] == "question" and f"@{kind[1].lower()}" not in body.lower():
            print(f"::warning::outbox: dropped {f.name} — a question file must @-mention its handle")
            continue
        if len(body) > MAX_COMMENT_CHARS:
            body = body[:MAX_COMMENT_CHARS] + "\n\n_(truncated by agent-ops: outbox comment over the size cap)_"
        if _norm(body) in seen:
            print(f"outbox: skipped {f.name} — an identical comment is already on the ticket")
            continue
        seen.add(_norm(body))
        chosen.append({"name": f.name, "kind": kind[0], "handle": kind[1], "body": body})
        if len(chosen) >= MAX_OUTBOX:
            print(f"::warning::outbox: cap of {MAX_OUTBOX} posts reached; remaining files dropped")
            break
    return chosen


def post_outbox(repo: str, issue: int, impl_repo: str, outbox: Path, result: str, people_path: str,
                run_url: str) -> int:
    people = load_people(people_path)
    try:
        comments = list_comments(repo, issue)
    except GhError as e:
        print(f"::warning::outbox: cannot list comments on {repo}#{issue} ({e}) — nothing posted")
        return 0
    chosen = select_outbox(outbox, result, people, [c.get("body") or "" for c in comments])
    if not chosen:
        print("outbox: nothing to post")
        return 0
    events = []
    for c in chosen:
        try:
            write_comment(repo, issue, c["body"], None)
        except GhError as e:
            print(f"::warning::outbox: could not post {c['name']} ({e})")
            continue
        who = f" for @{c['handle']}" if c["handle"] else ""
        print(f"outbox: posted {c['name']}")
        events.append({"event": "comment", "status": "-", "run_url": run_url,
                       "note": f"{c['kind'].replace('-', ' ')} posted{who} (from the drafter's outbox)"})
    if events:
        upsert(repo, issue, impl_repo, events, comments)
    return len(events)


# --------------------------------------------------------------------- cli ---

def parse_sets(pairs: list[str]) -> dict:
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"--set expects key=value, got {pair!r}")
        k, v = pair.split("=", 1)
        out[k] = coerce(k, v)
    return out


def cmd_upsert(a) -> int:
    upsert(a.repo, a.issue, a.impl_repo, [{"event": a.event, "status": a.status, "note": a.note,
                                            "run_url": a.run_url, "sets": parse_sets(a.set)}])
    return 0


def cmd_post_outbox(a) -> int:
    post_outbox(a.repo, a.issue, a.impl_repo, Path(a.dir), a.result or "", a.people, a.run_url)
    return 0


def cmd_render(a) -> int:
    p = json.loads(Path(a.payload).read_text(encoding="utf-8"))
    base = new_payload(int(p.get("issue", 0)), p.get("impl_repo", ""))
    base.update(p)
    sys.stdout.write(render(base))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--repo", required=True, help="ticket repo, owner/name")
        sp.add_argument("--issue", required=True, type=int)
        sp.add_argument("--impl-repo", required=True, help="implementation repo, owner/name (the claim key)")
        sp.add_argument("--run-url", default="")

    u = sub.add_parser("upsert")
    common(u)
    u.add_argument("--event", required=True, help="short slug, e.g. claimed, spec-pr-opened, retry, abandoned")
    u.add_argument("--status", default="-", help="new queue status, or - to keep")
    u.add_argument("--note", default="")
    u.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    u.set_defaults(fn=cmd_upsert)

    o = sub.add_parser("post-outbox")
    common(o)
    o.add_argument("--dir", required=True)
    o.add_argument("--result", default="", help="the drafter's RESULT token")
    o.add_argument("--people", required=True, help="agents/spec-drafter/named-people.yaml")
    o.set_defaults(fn=cmd_post_outbox)

    r = sub.add_parser("render")
    r.add_argument("--payload", required=True)
    r.set_defaults(fn=cmd_render)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
