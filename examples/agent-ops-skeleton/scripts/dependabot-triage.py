#!/usr/bin/env python3
"""Dependabot triage: deterministic classifier + actor for Dependabot PRs.

Dependabot PRs concentrate on whoever is the default reviewer. The policy: verify
CI, auto-merge minor/patch bumps, hand majors to a rotating human reviewer
(not the lead), and surface only what is broken. Everything a regex or a
status lookup can decide lives here with a unit test; the model is never in
the merge decision (see agents/dependabot-diagnoser/CLAUDE.md for the one
bounded node, which only explains a regression after this script found it).

GitHub is the state: exactly one of the deps:* labels per PR plus one
upserted marker comment carrying a JSON payload. No runtime state file.

Policy: state/dependabot-repos.json (schema: schemas/dependabot-repos.schema.json).
A repo absent from the policy is never touched. `verify_checks: []` means
label-only, never merge.

Subcommands
  classify --pr FILE --policy FILE --repo NAME [--main-checks FILE] [--mode M]
        Decide one PR from a saved `gh pr view --json ...` document. Prints the
        decision as JSON. --main-checks is {check_name: green|red|pending|skipped|unknown}.
  run --policy FILE --mode observe|act [--repos a,b] [--pr N] [--summary FILE] [--report FILE]
        Enumerate open Dependabot PRs on the given repos (default: every repo in
        the policy), decide each, act when --mode act, write the step-summary
        table and a JSON report. Observe mode issues no write call at all.
  diagnose-targets --report FILE
        Print the regression rows the workflow should run the diagnoser on.
  post-diagnosis --repo NAME --pr N --file diag.md [--mode M]
        Merge a diagnosis into the PR's marker comment (act mode only).

Outcomes (evaluated in this order): skip, needs-human, rebase, wait,
blocked:missing, blocked:main-red, blocked:regression, merge.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

OWNER = "<YOUR_ORG>"
DEPENDABOT_LOGINS = {"app/dependabot", "dependabot[bot]", "dependabot"}
BOT_SUFFIXES = ("[bot]",)

LABELS = {
    "deps:auto": (
        "0E8A16",
        "dependabot-triage: minor/patch bump, verify checks green — approved and merged by the bot",
    ),
    "deps:needs-human": (
        "FBCA04",
        "dependabot-triage: major / 0.x / unverifiable bump — a human reviewer decides",
    ),
    "deps:blocked": (
        "B60205",
        "dependabot-triage: a verification check is missing or red on this PR — see the bot comment",
    ),
}
MARKER_PREFIX = "<!-- agent-ops:dependabot-triage v1 "
MARKER_RE = re.compile(r"<!-- agent-ops:dependabot-triage v1 (\{.*?\}) -->", re.S)

PR_JSON_FIELDS = ("number,title,body,author,isDraft,state,labels,headRefOid,mergeable,"
                  "mergeStateStatus,statusCheckRollup,reviewRequests,latestReviews,url,baseRefName")

CLASS_ORDER = {"patch": 0, "minor": 1, "major": 2, "unparseable": 3}

# Dependabot body shapes (release notes sit inside <details>, whose lines
# never start with these words, so anchoring at ^ is what keeps them out):
#   Updates `pkg` from 1.2.3 to 1.3.0                      grouped / multi-dep
#   Bumps [pkg](https://…) from 1.2.3 to 1.3.0.            single
#   Bumps pkg from 1.2.3 to 1.3.0.                         single, no link
UPDATES_RE = re.compile(r"^Updates (?:\[`?([^`\]]+)`?\]\([^)]*\)|`([^`]+)`|(\S+)) from (\S+?) to (\S+?)\.?\s*$", re.M)
BUMPS_RE = re.compile(r"^Bumps (?:\[([^\]]+)\]\([^)]*\)|(\S+)) from (\S+?) to (\S+?)\.?\s*$", re.M)
TITLE_RE = re.compile(r"^(?:[a-z]+(?:\([^)]*\))?!?:\s*)?[Bb]ump (\S+) from (\S+) to (\S+)\s*$")
VERSION_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+.].*)?$")


# ------------------------------------------------------------ classification

def parse_version(s: str):
    m = VERSION_RE.match(s.strip())
    if not m:
        return None
    return tuple(int(x) if x is not None else 0 for x in m.groups())


def classify_version(frm: str, to: str, zero_x_minor_is_major: bool = True) -> str:
    a, b = parse_version(frm), parse_version(to)
    if a is None or b is None:
        return "unparseable"
    if a[0] != b[0]:
        return "major"
    if a[0] == 0 and zero_x_minor_is_major:
        # semver-0: minors are documented-breaking; on 0.0.x anything is
        if a[1] != b[1] or (a[1] == 0 and a[2] != b[2]):
            return "major"
    if a[1] != b[1]:
        return "minor"
    return "patch"


def parse_bumps(title: str, body: str) -> list[dict]:
    bumps = []
    for m in UPDATES_RE.finditer(body or ""):
        name = m.group(1) or m.group(2) or m.group(3)
        bumps.append({"name": name, "from": m.group(4), "to": m.group(5)})
    if not bumps:
        m = BUMPS_RE.search(body or "")
        if m:
            bumps.append({"name": m.group(1) or m.group(2), "from": m.group(3), "to": m.group(4)})
    if not bumps:
        m = TITLE_RE.match(title or "")
        if m:
            bumps.append({"name": m.group(1), "from": m.group(2), "to": m.group(3)})
    return bumps


def pr_class(bumps: list[dict], zero_x_minor_is_major: bool = True) -> str:
    if not bumps:
        return "unparseable"
    for b in bumps:
        b["class"] = classify_version(b["from"], b["to"], zero_x_minor_is_major)
    return max((b["class"] for b in bumps), key=CLASS_ORDER.__getitem__)


def normalize_checks(rollup: list[dict]) -> dict[str, dict]:
    """statusCheckRollup -> {name: {state, at, url, workflow}}; latest start wins."""
    out: dict[str, dict] = {}
    for c in rollup or []:
        if c.get("__typename") == "StatusContext" or "context" in c:
            name = c.get("context") or ""
            st = (c.get("state") or "").upper()
            state = {"SUCCESS": "green", "FAILURE": "red", "ERROR": "red"}.get(st, "pending")
            at = c.get("createdAt") or ""
            url, wf = c.get("targetUrl") or "", ""
        else:
            name = c.get("name") or ""
            if (c.get("status") or "").upper() != "COMPLETED":
                state = "pending"
            else:
                concl = (c.get("conclusion") or "").upper()
                if concl == "SUCCESS":
                    state = "green"
                elif concl in ("FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"):
                    state = "red"
                elif concl in ("SKIPPED", "NEUTRAL"):
                    state = "skipped"
                else:
                    state = "pending"
            at = c.get("startedAt") or ""
            url, wf = c.get("detailsUrl") or "", c.get("workflowName") or ""
        if not name:
            continue
        prev = out.get(name)
        if prev is None or at >= prev["at"]:
            out[name] = {"state": state, "at": at, "url": url, "workflow": wf}
    return out


def is_dependabot(pr: dict) -> bool:
    return ((pr.get("author") or {}).get("login") or "").lower() in DEPENDABOT_LOGINS


def existing_human_reviewer(pr: dict, exclude: set[str]) -> str | None:
    """A requested or past reviewer who is neither a bot nor excluded, else None."""
    logins = []
    for r in pr.get("reviewRequests") or []:
        if r.get("__typename", "User") == "User" and r.get("login"):
            logins.append(r["login"])
    for rv in pr.get("latestReviews") or []:
        login = (rv.get("author") or {}).get("login")
        if login:
            logins.append(login)
    for login in logins:
        if login.endswith(BOT_SUFFIXES) or login.startswith("app/"):
            continue
        if login in exclude:
            continue
        return login
    return None


def pick_reviewer(pr_number: int, reviewers: dict) -> str | None:
    out = set(reviewers.get("out") or [])
    active = [p for p in reviewers.get("pool") or [] if p not in out]
    if not active:
        return None
    return active[pr_number % len(active)]


def decide(  # noqa: C901 — pre-existing, not a lint-floor refactor
    pr: dict, repo_policy: dict | None, defaults: dict, main_state, *,
    reviewers: dict | None = None,
) -> dict:
    """Pure decision for one PR. main_state(check_name) -> green|red|pending|skipped|unknown."""
    d = {
        "number": pr.get("number"), "url": pr.get("url"), "title": pr.get("title"),
        "head": pr.get("headRefOid"), "class": None, "bumps": [], "verify": {},
        "outcome": None, "reason": None, "reviewer": None, "regression": None,
    }
    if not is_dependabot(pr):
        d.update(outcome="skip", reason="not a Dependabot PR")
        return d
    if repo_policy is None:
        d.update(outcome="skip", reason="repo not in policy")
        return d
    if (pr.get("state") or "OPEN") != "OPEN":
        d.update(outcome="skip", reason=f"PR is {pr.get('state')}")
        return d
    if pr.get("isDraft"):
        d.update(outcome="skip", reason="draft")
        return d

    zero_x = bool(defaults.get("zero_x_minor_is_major", True))
    bumps = parse_bumps(pr.get("title") or "", pr.get("body") or "")
    klass = pr_class(bumps, zero_x)
    d.update(bumps=bumps, **{"class": klass})

    reviewers = reviewers or {}
    exclude = set(reviewers.get("exclude") or []) | set(reviewers.get("out") or [])

    def needs_human(reason: str):
        d.update(outcome="needs-human", reason=reason)
        if existing_human_reviewer(pr, exclude) is None:
            d["reviewer"] = pick_reviewer(int(pr.get("number") or 0), reviewers)

    if klass == "unparseable":
        needs_human("could not parse a version bump from the PR body/title")
        return d
    if klass == "major":
        worst = [b for b in bumps if b["class"] == "major"]
        names = ", ".join(f"{b['name']} {b['from']}→{b['to']}" for b in worst[:4])
        reason = "major version bump" if len(worst) == 1 else f"{len(worst)} major bumps in the group"
        if any(parse_version(b["from"]) and parse_version(b["from"])[0] == 0 for b in worst):
            reason += " (0.x minor counts as major)"
        needs_human(f"{reason}: {names}")
        return d

    if (pr.get("mergeable") or "").upper() == "CONFLICTING":
        d.update(outcome="rebase", reason="merge conflict — ask Dependabot to rebase")
        return d

    verify_names = list(repo_policy.get("verify_checks") or [])
    if not verify_names:
        needs_human("repo has no verification checks configured — nothing can vouch for this bump")
        return d

    if pr.get("_checks_unavailable"):
        d.update(outcome="wait", reason=CHECKS_UNREADABLE_REASON)
        return d

    checks = normalize_checks(pr.get("statusCheckRollup") or [])
    verify = {}
    for n in verify_names:
        c = checks.get(n)
        verify[n] = c["state"] if c else "missing"
    d["verify"] = verify

    if (pr.get("mergeable") or "").upper() == "UNKNOWN":
        d.update(outcome="wait", reason="GitHub has not computed mergeability yet")
        return d
    if any(s == "pending" for s in verify.values()):
        d.update(outcome="wait", reason="verification checks still running: "
                 + ", ".join(n for n, s in verify.items() if s == "pending"))
        return d
    # Red is evaluated before missing: a downstream job skipped because an
    # upstream one failed is a consequence, not the finding. Only a CONFIRMED
    # red on main exonerates the PR — main often never runs the PR-only check
    # (a repo's `ci` can be skipped on main), and "cannot compare" must not park
    # a real regression as somebody else's problem.
    missing = [n for n, s in verify.items() if s in ("missing", "skipped")]
    red = [n for n, s in verify.items() if s == "red"]
    if red:
        exonerated, suspect = [], []
        for n in red:
            ms = main_state(n)
            (exonerated if ms == "red" else suspect).append((n, ms))
        if suspect:
            n, ms = suspect[0]
            d["regression"] = {"check": n, "url": checks[n]["url"], "workflow": checks[n]["workflow"],
                               "main_state": ms, "also_red_on_main": [m for m, _ in exonerated],
                               "downstream_skipped": missing}
            why = "green on main" if ms == "green" else f"main does not show it as red ({ms})"
            d.update(outcome="blocked:regression",
                     reason=f"`{n}` is red on this PR and {why} — treat as broken by the bump"
                     + (f"; skipped downstream: {', '.join(missing)}" if missing else ""))
            return d
        d.update(outcome="blocked:main-red",
                 reason="verification red here and confirmed red on main too: " + ", ".join(n for n, _ in exonerated))
        return d
    if missing:
        d.update(outcome="blocked:missing",
                 reason="verification check(s) absent or skipped on this head: " + ", ".join(missing))
        return d

    d.update(outcome="merge", reason=f"{klass} bump, verification green: " + ", ".join(verify_names))
    return d


# ------------------------------------------------------------------- gh io

class GhError(RuntimeError):
    pass


def gh(*args: str, input_text: str | None = None) -> str:
    p = subprocess.run(["gh", *args], capture_output=True, text=True, input=input_text)
    if p.returncode != 0:
        raise GhError(f"gh {' '.join(args[:4])}…: {p.stderr.strip()[:400]}")
    return p.stdout


def repo_full(repo: str) -> str:
    return repo if "/" in repo else f"{OWNER}/{repo}"


PR_JSON_FIELDS_NO_CHECKS = PR_JSON_FIELDS.replace("statusCheckRollup,", "")
CHECKS_UNREADABLE_REASON = ("check results are not readable — the example-app-bot App lacks `Checks: read` "
                            "(SETUP.md §1); majors are still routed, minor/patch bumps wait")


def _checks_unreadable(e: GhError) -> bool:
    # Without the App's Checks permission, GraphQL rejects the whole query on
    # private/internal repos ("Resource not accessible by integration
    # (…statusCheckRollup…)"). Public repos answer regardless.
    return "statusCheckRollup" in str(e)


def list_dependabot_prs(repo: str) -> list[dict]:
    args = ("pr", "list", "-R", repo_full(repo), "--author", "app/dependabot", "--state", "open", "--limit", "100")
    try:
        return json.loads(gh(*args, "--json", PR_JSON_FIELDS) or "[]")
    except GhError as e:
        if not _checks_unreadable(e):
            raise
    print(f"::warning::{repo}: {CHECKS_UNREADABLE_REASON}")
    prs = json.loads(gh(*args, "--json", PR_JSON_FIELDS_NO_CHECKS) or "[]")
    for p in prs:
        p["_checks_unavailable"] = True
    return prs


def refresh_pr(repo: str, number: int) -> dict:
    args = ("pr", "view", str(number), "-R", repo_full(repo))
    try:
        return json.loads(gh(*args, "--json", PR_JSON_FIELDS))
    except GhError as e:
        if not _checks_unreadable(e):
            raise
    pr = json.loads(gh(*args, "--json", PR_JSON_FIELDS_NO_CHECKS))
    pr["_checks_unavailable"] = True
    return pr


def repo_settings(repo: str) -> dict:
    try:
        return json.loads(gh("api", f"repos/{repo_full(repo)}",
                             "--jq", "{allow_squash_merge, allow_merge_commit, default_branch}"))
    except GhError as e:
        return {"error": str(e)}


def main_check_state(repo: str, base: str, check_name: str, _cache: dict) -> str:
    key = (repo, base, check_name)
    if key in _cache:
        return _cache[key]
    q = urllib.parse.quote(check_name, safe="")
    try:
        runs = json.loads(gh("api", f"repos/{repo_full(repo)}/commits/{base}/check-runs?check_name={q}&per_page=20",
                             "--jq", ".check_runs"))
    except GhError:
        _cache[key] = "unknown"
        return "unknown"
    runs = [r for r in runs or [] if r.get("name") == check_name]
    if not runs:
        _cache[key] = "unknown"
        return "unknown"
    latest = max(runs, key=lambda r: r.get("started_at") or "")
    if latest.get("status") != "completed":
        st = "pending"
    else:
        concl = (latest.get("conclusion") or "").lower()
        st = "green" if concl == "success" else "skipped" if concl in ("skipped", "neutral") else "red"
    _cache[key] = st
    return st


# ----------------------------------------------------------------- actions

def ensure_labels(repo: str) -> None:
    for name, (color, desc) in LABELS.items():
        try:
            gh("label", "create", name, "-R", repo_full(repo), "--color", color, "--description", desc, "--force")
        except GhError as e:
            print(f"::warning::{repo}: could not ensure label {name}: {e}")


def set_label(repo: str, pr: dict, label: str | None) -> None:
    have = {label.get("name") for label in pr.get("labels") or []}
    args = ["pr", "edit", str(pr["number"]), "-R", repo_full(repo)]
    changed = False
    for other in LABELS:
        if other != label and other in have:
            args += ["--remove-label", other]
            changed = True
    if label and label not in have:
        args += ["--add-label", label]
        changed = True
    if changed:
        gh(*args)


def request_reviewer(repo: str, number: int, login: str) -> None:
    gh("pr", "edit", str(number), "-R", repo_full(repo), "--add-reviewer", login)


def find_marker_comment(repo: str, number: int) -> tuple[int | None, dict | None]:
    out = gh("api", f"repos/{repo_full(repo)}/issues/{number}/comments", "--paginate",
             "--jq", ".[] | {id, body}")
    for line in out.splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        m = MARKER_RE.search(c.get("body") or "")
        if m:
            try:
                return c["id"], json.loads(m.group(1))
            except json.JSONDecodeError:
                return c["id"], {}
    return None, None


def render_comment(payload: dict, d: dict, mode: str, extra: str = "") -> str:
    observe_suffix = " *(observe mode — no action taken)*" if mode != "act" else ""
    lines = [f"{MARKER_PREFIX}{json.dumps(payload, sort_keys=True)} -->",
             f"**Dependabot triage** — `{d['outcome']}`" + observe_suffix,
             "", d["reason"] or ""]
    if d.get("bumps"):
        lines += ["", "| Package | From | To | Bump |", "|---|---|---|---|"]
        lines += [f"| `{b['name']}` | {b['from']} | {b['to']} | {b.get('class', '')} |" for b in d["bumps"]]
    if d.get("verify"):
        lines += ["", "Verification: " + ", ".join(f"`{n}` {s}" for n, s in d["verify"].items())]
    if d.get("reviewer"):
        lines += ["", f"Reviewer (round-robin): @{d['reviewer']}"]
    if extra:
        lines += ["", extra.rstrip()]
    lines += [
        "",
        "_Policy: `state/dependabot-repos.json` in agent-ops. Labels `deps:*` "
        "are the state; this comment is rewritten each run._",
    ]
    return "\n".join(lines)


def upsert_comment(repo: str, number: int, body: str, existing_id: int | None) -> None:
    if existing_id:
        gh("api", "-X", "PATCH", f"repos/{repo_full(repo)}/issues/comments/{existing_id}", "-f", f"body={body}")
    else:
        gh("api", "-X", "POST", f"repos/{repo_full(repo)}/issues/{number}/comments", "-f", f"body={body}")


def approve_and_merge(repo: str, d: dict, merge_method: str) -> tuple[bool, str]:
    fresh = refresh_pr(repo, d["number"])
    if fresh.get("headRefOid") != d["head"]:
        return False, "head moved since classification — re-evaluated next run"
    if fresh.get("state") != "OPEN":
        return False, f"PR is {fresh.get('state')}"
    try:
        gh("pr", "review", str(d["number"]), "-R", repo_full(repo), "--approve",
           "--body", "dependabot-triage: minor/patch bump, verification checks green "
           "(policy: agent-ops state/dependabot-repos.json)")
    except GhError as e:
        return False, f"approve failed: {e}"
    try:
        gh("pr", "merge", str(d["number"]), "-R", repo_full(repo), f"--{merge_method}",
           "--match-head-commit", d["head"])
    except GhError as e:
        return False, f"merge failed: {e}"
    return True, "merged"


# --------------------------------------------------------------------- run

OUTCOME_LABEL = {
    "needs-human": "deps:needs-human",
    "blocked:missing": "deps:blocked",
    "blocked:regression": "deps:blocked",
}


def act_on(  # noqa: C901 — pre-existing, not a lint-floor refactor
    repo: str, pr: dict, d: dict, policy: dict, mode: str, counters: dict, frozen: bool
) -> None:
    """Fill d['action'] and, in act mode, perform it."""
    repo_policy = policy["repos"][repo]
    defaults = policy.get("defaults") or {}
    automerge = repo_policy.get("automerge", defaults.get("automerge", False))
    merge_method = repo_policy.get("merge_method", defaults.get("merge_method", "squash"))
    cap_repo = int(defaults.get("max_merges_per_repo_per_run", 3))
    cap_all = int(defaults.get("max_merges_per_run", 10))
    o = d["outcome"]

    if o == "skip" or o == "wait" or o == "blocked:main-red":
        d["action"] = "none"
        return
    if o == "rebase":
        d["action"] = "comment @dependabot rebase"
    elif o == "merge":
        if not automerge:
            d["action"] = "label deps:needs-human (automerge disabled for this repo)"
            if existing_human_reviewer(pr, set((policy.get("reviewers") or {}).get("exclude") or [])) is None:
                d["reviewer"] = pick_reviewer(int(pr["number"]), policy.get("reviewers") or {})
        elif frozen:
            d["action"] = "hold (AUTO_MERGE_FROZEN)"
        elif counters["repo"].get(repo, 0) >= cap_repo or counters["all"] >= cap_all:
            d["action"] = "hold (merge cap reached this run)"
        else:
            d["action"] = f"approve + {merge_method} merge"
    else:
        d["action"] = f"label {OUTCOME_LABEL[o]}" + (f", request @{d['reviewer']}" if d.get("reviewer") else "")

    if mode != "act":
        return

    marker_id, payload = find_marker_comment(repo, pr["number"])
    payload = payload or {}
    new_payload = {"sha": d["head"], "class": d["class"], "outcome": o,
                   "rebase_requested_sha": payload.get("rebase_requested_sha"),
                   "diagnosed_sha": payload.get("diagnosed_sha")}

    if o == "rebase":
        if payload.get("rebase_requested_sha") == d["head"]:
            d["action"] = "rebase already requested for this head"
            return
        gh("api", "-X", "POST", f"repos/{repo_full(repo)}/issues/{pr['number']}/comments",
           "-f", "body=@dependabot rebase")
        new_payload["rebase_requested_sha"] = d["head"]
        upsert_comment(repo, pr["number"], render_comment(new_payload, d, mode), marker_id)
        return

    if o == "merge" and d["action"].startswith("approve"):
        set_label(repo, pr, "deps:auto")
        ok, msg = approve_and_merge(repo, d, merge_method)
        d["action"] = f"approve + {merge_method} merge → {msg}"
        if ok:
            counters["repo"][repo] = counters["repo"].get(repo, 0) + 1
            counters["all"] += 1
        else:
            print(f"::warning::{repo}#{pr['number']}: {msg}")
        return

    label = OUTCOME_LABEL.get(o) or ("deps:needs-human" if o == "merge" else None)
    if o == "merge" and not d["action"].startswith("label"):
        label = None  # holds: leave labels alone
    if label:
        set_label(repo, pr, label)
    if d.get("reviewer") and label == "deps:needs-human":
        try:
            request_reviewer(repo, pr["number"], d["reviewer"])
        except GhError as e:
            print(f"::warning::{repo}#{pr['number']}: could not request @{d['reviewer']}: {e}")
    if payload != new_payload or marker_id is None:
        extra = ""
        if payload.get("diagnosed_sha") == d["head"] and payload.get("diagnosis"):
            new_payload["diagnosis"] = payload["diagnosis"]
            extra = payload["diagnosis"]
        upsert_comment(repo, pr["number"], render_comment(new_payload, d, mode, extra), marker_id)


def write_summary(path: str, rows: list[dict], repo_headers: dict, mode: str, skipped_repos: list[str]) -> None:
    lines = [f"### Dependabot triage — mode `{mode}`", ""]
    if skipped_repos:
        skipped = ", ".join(f"`{r}`" for r in skipped_repos)
        lines += ["Repos skipped (example-app-bot App not installed): " + skipped, ""]
    for repo, h in repo_headers.items():
        verify_checks = (
            ", ".join(f"`{c}`" for c in h.get("verify_checks") or []) or "*(none — label-only)*"
        )
        main_red = f" · verify red on main: {', '.join(h['main_red'])}" if h.get("main_red") else ""
        lines.append(
            f"- `{repo}` — squash allowed: {h.get('allow_squash_merge')} · "
            f"default branch: `{h.get('default_branch')}` · "
            f"verify checks: {verify_checks}"
            + main_red
        )
    lines += [
        "",
        "| Repo | PR | Class | Bumps | Verify | Outcome | Action | Reviewer |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        bumps = "; ".join(f"{b['name']} {b['from']}→{b['to']}" for b in r["bumps"][:3])
        bumps += " …" if len(r["bumps"]) > 3 else ""
        verify = ", ".join(f"{n}={s}" for n, s in (r.get("verify") or {}).items()) or "—"
        reviewer = ("@" + r["reviewer"]) if r.get("reviewer") else "—"
        lines.append(
            f"| {r['repo']} | [#{r['number']}]({r['url']}) | {r['class'] or '—'} | {bumps or '—'} | {verify} | "
            f"`{r['outcome']}` | {r.get('action') or '—'} | {reviewer} |"
        )
    totals: dict[str, int] = {}
    for r in rows:
        totals[r["outcome"]] = totals.get(r["outcome"], 0) + 1
    lines += ["", "Totals: " + ", ".join(f"`{k}` {v}" for k, v in sorted(totals.items())) + f" · {len(rows)} PRs"]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def cmd_run(a) -> int:  # noqa: C901 — pre-existing, not a lint-floor refactor
    policy = json.loads(Path(a.policy).read_text())
    mode = "act" if a.mode == "act" else "observe"
    frozen = (os.environ.get("AUTO_MERGE_FROZEN") or "").strip().lower() == "true"
    repos = [r.strip() for r in (a.repos or "").split(",") if r.strip()] or list(policy["repos"].keys())
    skipped = [r for r in repos if r not in policy["repos"]]
    repos = [r for r in repos if r in policy["repos"]]
    rows, headers = [], {}
    counters = {"repo": {}, "all": 0}
    main_cache: dict = {}
    reviewers = policy.get("reviewers") or {}
    defaults = policy.get("defaults") or {}

    for repo in repos:
        rp = policy["repos"][repo]
        settings = repo_settings(repo)
        base = settings.get("default_branch") or "main"
        headers[repo] = {**settings, "verify_checks": rp.get("verify_checks") or [], "main_red": []}
        try:
            prs = list_dependabot_prs(repo)
        except GhError as e:
            print(f"::warning::{repo}: cannot list PRs — {e}")
            headers[repo]["error"] = str(e)
            continue
        if a.pr:
            prs = [p for p in prs if str(p.get("number")) == str(a.pr)]
        if mode == "act" and prs:
            ensure_labels(repo)
        for pr in prs:
            if (pr.get("mergeable") or "").upper() == "UNKNOWN":
                time.sleep(2)
                try:
                    pr = refresh_pr(repo, pr["number"])
                except GhError:
                    pass
            def ms(n, _r=repo, _b=base):
                return main_check_state(_r, _b, n, main_cache)
            d = decide(pr, rp, defaults, ms, reviewers=reviewers)
            d["repo"] = repo
            if d["outcome"] == "blocked:main-red":
                for n in (d.get("verify") or {}):
                    if d["verify"][n] == "red" and n not in headers[repo]["main_red"]:
                        headers[repo]["main_red"].append(n)
            try:
                act_on(repo, pr, d, policy, mode, counters, frozen)
            except GhError as e:
                d["action"] = f"FAILED: {e}"
                print(f"::warning::{repo}#{pr['number']}: {e}")
            rows.append(d)
            print(
                f"{repo}#{pr['number']:<5} {d['class'] or '-':<11} {d['outcome']:<19} "
                f"{d.get('action') or ''}  — {d['reason']}"
            )

    if a.summary:
        write_summary(a.summary, rows, headers, mode, skipped)
    if a.report:
        report = {"mode": mode, "rows": rows, "repos": headers, "skipped_repos": skipped}
        Path(a.report).write_text(json.dumps(report, indent=1))
    print(f"\n{len(rows)} PR(s) across {len(repos)} repo(s); merges this run: {counters['all']}; mode={mode}")
    return 0


def cmd_classify(a) -> int:
    pr = json.loads(Path(a.pr).read_text())
    policy = json.loads(Path(a.policy).read_text())
    main = json.loads(Path(a.main_checks).read_text()) if a.main_checks else {}
    d = decide(pr, policy["repos"].get(a.repo), policy.get("defaults") or {},
               lambda n: main.get(n, "unknown"), reviewers=policy.get("reviewers") or {})
    d["repo"] = a.repo
    if d["outcome"] not in ("skip",):
        act_on(a.repo, pr, d, policy, "observe", {"repo": {}, "all": 0}, False)
    print(json.dumps(d, indent=1))
    return 0


def cmd_diagnose_targets(a) -> int:
    rep = json.loads(Path(a.report).read_text())
    targets = [{"repo": r["repo"], "number": r["number"], "head": r["head"], **r["regression"], "bumps": r["bumps"]}
               for r in rep["rows"] if r["outcome"] == "blocked:regression" and r.get("regression")]
    print(json.dumps(targets))
    return 0


def cmd_post_diagnosis(a) -> int:
    if a.mode != "act":
        print("observe mode — diagnosis not posted")
        return 0
    text = Path(a.file).read_text().strip()
    if not text:
        return 0
    if re.search(r"claude|anthropic", text, re.I):
        print("::warning::diagnosis mentions the model vendor — not posted (hard rule 5)")
        return 0
    marker_id, payload = find_marker_comment(a.repo, int(a.pr))
    if marker_id is None or payload is None:
        print("::warning::no marker comment to attach the diagnosis to")
        return 0
    pr = refresh_pr(a.repo, int(a.pr))
    if payload.get("sha") != pr.get("headRefOid"):
        print("head moved since the diagnosis was produced — skipped")
        return 0
    payload["diagnosed_sha"] = payload["sha"]
    payload["diagnosis"] = "**Why it broke (automated read of the failing job log):**\n\n" + text
    d = {"outcome": payload.get("outcome"), "reason": None, "bumps": [], "verify": {}, "class": payload.get("class")}
    # Re-render from the stored payload only; keep the human-facing reason short.
    body = render_comment(payload, {**d, "reason": "See the diagnosis below."}, "act", payload["diagnosis"])
    upsert_comment(a.repo, int(a.pr), body, marker_id)
    print(f"diagnosis posted on {a.repo}#{a.pr}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify")
    c.add_argument("--pr", required=True)
    c.add_argument("--policy", required=True)
    c.add_argument("--repo", required=True)
    c.add_argument("--main-checks")
    c.set_defaults(fn=cmd_classify)
    r = sub.add_parser("run")
    r.add_argument("--policy", required=True)
    r.add_argument("--mode", default="observe")
    r.add_argument("--repos")
    r.add_argument("--pr")
    r.add_argument("--summary")
    r.add_argument("--report")
    r.set_defaults(fn=cmd_run)
    t = sub.add_parser("diagnose-targets")
    t.add_argument("--report", required=True)
    t.set_defaults(fn=cmd_diagnose_targets)
    p = sub.add_parser("post-diagnosis")
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--mode", default="observe")
    p.set_defaults(fn=cmd_post_diagnosis)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
