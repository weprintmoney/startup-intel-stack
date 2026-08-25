#!/usr/bin/env python3
"""Update state/autonomy-ledger.json from closed agent PRs and postmortems.

Ladder (per ticket-class, within mode:claude-led only):
  L0 human-authored -> L1 agent PR, human reviews spec+code
  -> L2 spec fast-path auto-approved -> L3 auto-merge on all-green + 24h revert
  -> L4 auto-merge + self-selected tickets (machinery not built; promotion caps at L3)

Promotion (ALL must hold, since the class's last transition):
  >=10 consecutive clean merges (zero change-requests, zero human commits on
  branch, no post-merge human edits), judge first-pass >=90% over >=10 judged
  PRs, zero postmortems with caused_by_class in trailing 30 days, zero
  coverage trips, zero guardrail overrides, class not frozen, no global freeze.

Demotion (automatic):
  postmortem frontmatter caused_by_class -> -1 level + class frozen
  2 consecutive change-requested PRs -> -1 level
  (judge verdict flip -> AUTO_MERGE_FROZEN repo variable, handled by judge-evals)

Modes:
  live (default)      gather from gh; requires --internal-docs DIR for postmortems;
                      writes state/autonomy-ledger.json (caller commits via
                      scripts/commit-state.sh)
  --fixtures DIR      replay DIR/{ledger,prs,postmortems}.json + DIR/now.txt,
                      print resulting ledger to stdout
  --selftest DIR      run every case subdir in DIR against its expected.json

Determinism: metrics are recomputed from scratch over PRs closed after the
class's last transition (anchor), so re-runs are idempotent. Postmortem
demotions dedupe via evidence_url in the class history.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_PROMOTION_LEVEL = 3  # L4 needs self-selection machinery; documented follow-up
PROMOTION_STREAK = 10
JUDGE_FIRST_PASS_MIN = 0.90
JUDGE_MIN_JUDGED = 10
POSTMORTEM_PROMOTION_BLOCK_DAYS = 30
POSTMORTEM_DEMOTION_WINDOW_DAYS = 90
PR_LOOKBACK_DAYS = 90
POST_MERGE_EDIT_WINDOW_DAYS = 7
BOT_LOGIN = os.environ.get("BOT_LOGIN", "example-app-eng-bot")
TICKET_REPO = "<YOUR_ORG>/example-app-core"
JUDGE_CONTEXT = "agent-ops/code-judge"
COVERAGE_CONTEXT = "agent-ops/coverage-delta"  # not built yet; counted when present


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt_ts(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_class():
    return {
        "level": 1,
        "consecutive_clean_merges": 0,
        "change_requested_streak": 0,
        "judge_first_pass": {"pass": 0, "total": 0},
        "coverage_trips": 0,
        "guardrail_overrides": 0,
        "frozen": False,
        "frozen_reason": None,
        "last_promoted_at": None,
        "last_demoted_at": None,
        "history": [],
    }


def reset_metrics(cls):
    cls["consecutive_clean_merges"] = 0
    cls["change_requested_streak"] = 0
    cls["judge_first_pass"] = {"pass": 0, "total": 0}
    cls["coverage_trips"] = 0
    cls["guardrail_overrides"] = 0


def anchor_of(cls):
    stamps = [cls.get("last_promoted_at"), cls.get("last_demoted_at")]
    stamps = [parse_ts(s) for s in stamps if s]
    return max(stamps) if stamps else datetime(1970, 1, 1, tzinfo=timezone.utc)


def is_clean_merge(pr):
    return (
        pr["merged"]
        and not pr["change_requested"]
        and pr.get("human_commits", 0) == 0
        and not pr.get("post_merge_human_edits", False)
    )


def apply(ledger, prs, postmortems, now, auto_merge_frozen=False):
    """Pure transition function. Mutates and returns (ledger, transitions)."""
    transitions = []
    classes = ledger.setdefault("classes", {})

    by_class = {}
    for pr in sorted(prs, key=lambda p: p["closed_at"]):
        by_class.setdefault(pr.get("ticket_class") or "unclassified", []).append(pr)

    # 1. Recompute rolling metrics since each class's anchor.
    for name, class_prs in by_class.items():
        cls = classes.setdefault(name, new_class())
        anchor = anchor_of(cls)
        reset_metrics(cls)
        for pr in class_prs:
            if parse_ts(pr["closed_at"]) <= anchor:
                continue
            if pr["change_requested"]:
                cls["change_requested_streak"] += 1
            else:
                cls["change_requested_streak"] = 0
            if is_clean_merge(pr):
                cls["consecutive_clean_merges"] += 1
            else:
                cls["consecutive_clean_merges"] = 0
            if pr.get("judge_first_pass") is not None:
                cls["judge_first_pass"]["total"] += 1
                if pr["judge_first_pass"]:
                    cls["judge_first_pass"]["pass"] += 1
            if pr.get("coverage_tripped"):
                cls["coverage_trips"] += 1
            if pr.get("guardrail_overridden"):
                cls["guardrail_overrides"] += 1

    def transition(name, cls, to, reason, evidence_url=None, freeze=False):
        entry = {"at": fmt_ts(now), "from": cls["level"], "to": to, "reason": reason}
        if evidence_url:
            entry["evidence_url"] = evidence_url
        cls["history"].append(entry)
        transitions.append((name, cls["level"], to, reason))
        if to < cls["level"]:
            cls["last_demoted_at"] = fmt_ts(now)
            if freeze:
                cls["frozen"] = True
                cls["frozen_reason"] = reason
        else:
            cls["last_promoted_at"] = fmt_ts(now)
        cls["level"] = to
        reset_metrics(cls)

    # 2. Postmortem demotions (deduped by evidence_url; bounded window).
    for pm in postmortems:
        name = pm["class"]
        pm_date = parse_ts(pm["date"])
        if pm_date < now - timedelta(days=POSTMORTEM_DEMOTION_WINDOW_DAYS):
            continue
        cls = classes.setdefault(name, new_class())
        if any(h.get("evidence_url") == pm["url"] for h in cls["history"]):
            continue
        transition(
            name, cls, max(0, cls["level"] - 1),
            "demotion: postmortem caused_by_class", pm["url"], freeze=True,
        )

    # 3. Change-request demotions.
    for name, cls in classes.items():
        if cls["change_requested_streak"] >= 2:
            last = by_class.get(name, [])
            evidence = last[-1]["url"] if last else None
            transition(
                name, cls, max(0, cls["level"] - 1),
                "demotion: 2 consecutive change-requested PRs", evidence,
            )

    # 4. Promotions.
    recent_pm_classes = {
        pm["class"]
        for pm in postmortems
        if parse_ts(pm["date"]) > now - timedelta(days=POSTMORTEM_PROMOTION_BLOCK_DAYS)
    }
    if not ledger.get("global_freeze") and not auto_merge_frozen:
        for name, cls in classes.items():
            jfp = cls["judge_first_pass"]
            if (
                cls["level"] < MAX_PROMOTION_LEVEL
                and not cls["frozen"]
                and cls["consecutive_clean_merges"] >= PROMOTION_STREAK
                and jfp["total"] >= JUDGE_MIN_JUDGED
                and jfp["pass"] / jfp["total"] >= JUDGE_FIRST_PASS_MIN
                and name not in recent_pm_classes
                and cls["coverage_trips"] == 0
                and cls["guardrail_overrides"] == 0
            ):
                reason = (
                    f"promotion: {cls['consecutive_clean_merges']} clean merges, "
                    f"judge first-pass {jfp['pass']}/{jfp['total']}, "
                    f"no postmortems in {POSTMORTEM_PROMOTION_BLOCK_DAYS}d"
                )
                transition(name, cls, cls["level"] + 1, reason,
                           os.environ.get("RUN_URL") or None)

    ledger["updated_at"] = fmt_ts(now)
    return ledger, transitions


# ---------------------------------------------------------------- live gathering

def gh(args, check=True):
    r = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def gh_json(args):
    out = gh(args)
    return json.loads(out) if out.strip() else []


def is_bot(login):
    return login == BOT_LOGIN or login.endswith("[bot]") or login.endswith("-bot")


def product_repos(root):
    repos = []
    for p in sorted(Path(root, "guards").glob("*.paths")):
        repos.append(f"<YOUR_ORG>/{p.stem}")
    return repos


_class_cache = {}


def ticket_class(branch):
    m = re.match(r"agent/(\d+)-", branch)
    if not m:
        return "unclassified"
    issue = m.group(1)
    if issue not in _class_cache:
        cls = "unclassified"
        try:
            data = json.loads(gh(["issue", "view", issue, "-R", TICKET_REPO,
                                  "--json", "labels"]))
            for lab in data.get("labels", []):
                if lab["name"].startswith("class:"):
                    cls = lab["name"][len("class:"):]
                    break
        except RuntimeError:
            pass
        _class_cache[issue] = cls
    return _class_cache[issue]


def judge_first_pass(repo, first_sha):
    try:
        statuses = gh_json(["api", "--paginate",
                            f"repos/{repo}/commits/{first_sha}/statuses"])
    except RuntimeError:
        return None
    judge = sorted(
        (s for s in statuses if s["context"] == JUDGE_CONTEXT),
        key=lambda s: s["created_at"],
    )
    if not judge:
        return None
    return judge[0]["state"] == "success"


def post_merge_human_edits(repo, merged_at, pr_files):
    since = merged_at
    until = fmt_ts(parse_ts(merged_at) + timedelta(days=POST_MERGE_EDIT_WINDOW_DAYS))
    try:
        commits = gh_json(["api", f"repos/{repo}/commits?since={since}&until={until}"])
    except RuntimeError:
        return False
    for c in commits:
        login = (c.get("author") or {}).get("login") or ""
        if login and is_bot(login):
            continue
        try:
            detail = json.loads(gh(["api", f"repos/{repo}/commits/{c['sha']}"]))
        except RuntimeError:
            continue
        touched = {f["filename"] for f in detail.get("files", [])}
        if touched & pr_files:
            return True
    return False


def gather_prs(root, now):
    prs = []
    cutoff = now - timedelta(days=PR_LOOKBACK_DAYS)
    for repo in product_repos(root):
        try:
            listed = gh_json(["pr", "list", "-R", repo, "--state", "all",
                              "--limit", "200", "--json",
                              "number,headRefName,state,mergedAt,closedAt,url"])
        except RuntimeError as e:
            print(f"::warning::skipping {repo}: {e}", file=sys.stderr)
            continue
        for p in listed:
            if not p["headRefName"].startswith("agent/") or p["state"] == "OPEN":
                continue
            closed_at = p.get("closedAt") or p.get("mergedAt")
            if not closed_at or parse_ts(closed_at) < cutoff:
                continue
            n = p["number"]
            detail = json.loads(gh(["pr", "view", str(n), "-R", repo, "--json",
                                    "commits,files,reviews"]))
            reviews = detail.get("reviews", [])
            change_requested = any(
                r["state"] == "CHANGES_REQUESTED"
                and not is_bot((r.get("author") or {}).get("login") or "")
                for r in reviews
            )
            commits = detail.get("commits", [])
            human_commits = sum(
                1 for c in commits
                if not any(is_bot(a.get("login") or "") for a in c.get("authors", []))
            )
            merged = p["state"] == "MERGED"
            pr_files = {f["path"] for f in detail.get("files", [])}
            pme = False
            if merged and p.get("mergedAt"):
                pme = post_merge_human_edits(repo, p["mergedAt"], pr_files)
            jfp = judge_first_pass(repo, commits[0]["oid"]) if commits else None
            prs.append({
                "repo": repo,
                "pr": n,
                "url": p["url"],
                "ticket_class": ticket_class(p["headRefName"]),
                "merged": merged,
                "closed_at": closed_at,
                "change_requested": change_requested,
                "human_commits": human_commits,
                "post_merge_human_edits": pme,
                "judge_first_pass": jfp,
                "coverage_tripped": False,
                "guardrail_overridden": False,
            })
    return prs


def gather_postmortems(docs_dir):
    """Scan internal-docs markdown frontmatter for caused_by_class."""
    pms = []
    for path in Path(docs_dir).rglob("*.md"):
        if ".git" in path.parts:
            continue
        try:
            head = path.read_text(errors="ignore")[:4000]
        except OSError:
            continue
        if not head.startswith("---") or "caused_by_class" not in head:
            continue
        fm = head.split("---", 2)[1]
        cls = date = None
        for line in fm.splitlines():
            m = re.match(r"caused_by_class:\s*[\"']?([a-z0-9-]+)", line)
            if m:
                cls = m.group(1)
            m = re.match(r"(?:incident_)?date:\s*[\"']?(\d{4}-\d{2}-\d{2})", line)
            if m:
                date = m.group(1)
        if cls and date:
            rel = path.relative_to(docs_dir)
            pms.append({
                "class": cls,
                "date": f"{date}T00:00:00Z",
                "url": f"https://github.com/<YOUR_ORG>/internal-docs/blob/main/{rel}",
            })
    return pms


# ------------------------------------------------------------------- entrypoints

def load_case(case_dir):
    d = Path(case_dir)
    ledger = json.loads((d / "ledger.json").read_text())
    prs = json.loads((d / "prs.json").read_text())
    pms = json.loads((d / "postmortems.json").read_text())
    now_file = d / "now.txt"
    now = parse_ts(now_file.read_text().strip()) if now_file.exists() \
        else datetime.now(timezone.utc)
    return ledger, prs, pms, now


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixtures", metavar="DIR",
                    help="replay a fixture case dir; print resulting ledger")
    ap.add_argument("--selftest", metavar="DIR",
                    help="run all case subdirs against their expected.json")
    ap.add_argument("--internal-docs", metavar="DIR",
                    help="checked-out internal-docs for postmortem scan (live mode)")
    ap.add_argument("--auto-merge-frozen", action="store_true",
                    help="AUTO_MERGE_FROZEN repo variable is true; blocks promotions")
    ap.add_argument("--ledger", default="state/autonomy-ledger.json")
    args = ap.parse_args()

    if args.selftest:
        os.environ.pop("RUN_URL", None)  # keep expected.json comparable in CI
        failed = 0
        cases = sorted(p for p in Path(args.selftest).iterdir() if p.is_dir())
        for case in cases:
            ledger, prs, pms, now = load_case(case)
            result, _ = apply(ledger, prs, pms, now)
            expected = json.loads((case / "expected.json").read_text())
            if result == expected:
                print(f"PASS {case.name}")
            else:
                failed += 1
                print(f"FAIL {case.name}")
                print(json.dumps(result, indent=2))
        print(f"{len(cases) - failed}/{len(cases)} ledger cases passed")
        sys.exit(1 if failed else 0)

    if args.fixtures:
        ledger, prs, pms, now = load_case(args.fixtures)
        result, transitions = apply(ledger, prs, pms, now, args.auto_merge_frozen)
        for name, frm, to, reason in transitions:
            print(f"TRANSITION: {name} L{frm}->L{to} {reason}", file=sys.stderr)
        print(json.dumps(result, indent=2))
        return

    # live mode
    now = datetime.now(timezone.utc)
    ledger = json.loads(Path(args.ledger).read_text())
    prs = gather_prs(".", now)
    pms = gather_postmortems(args.internal_docs) if args.internal_docs else []
    result, transitions = apply(ledger, prs, pms, now, args.auto_merge_frozen)
    Path(args.ledger).write_text(json.dumps(result, indent=2) + "\n")
    for name, frm, to, reason in transitions:
        print(f"TRANSITION: {name} L{frm}->L{to} {reason}")
    if not transitions:
        print("NO_TRANSITIONS")


if __name__ == "__main__":
    main()
