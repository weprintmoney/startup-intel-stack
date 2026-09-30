#!/usr/bin/env python3
"""Pipeline heartbeat: absence-alerting for agent-ops's scheduled workflows.

GitHub alerts when a workflow RUN fails, but says nothing when a schedule
silently stops firing. This checks:
  1. staleness — no successful run of a monitored workflow within its window
  2. latest completed run of a monitored workflow failed
Silence = healthy. Alerts go to the failure-alerts Slack channel via
scripts/slack-alert.sh — the one canonical Slack implementation. Every workflow that posts
to Slack goes through that one script.

While AGENT_OPS_PAUSED=true, every pause-gated workflow concludes `skipped`
and can never produce a fresh success, so its staleness window is
uninformative; those checks are skipped and reported as one log line
instead. Gating is read from the workflow file itself, so a newly gated
workflow needs no edit here.
"""

import json
import os
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

# workflow file -> max hours since last successful run, or None for
# on-demand workflows that have no schedule: those are checked only for
# "latest completed run failed" (the whole delivery loop
# and most eval suites would otherwise be unmonitored).
MONITORED = {
    # scheduled
    "cost-digest.yml": 204,  # Mon 8am ET weekly
    "ticket-intake.yml": 5,  # cron every 2h (+ slack for runner delay)
    "spec-pending-reap.yml": 3,  # cron every 30 min
    "pr-merged-reap.yml": 3,  # cron every 30 min
    "spec-draft-orchestrator.yml": 3,  # cron every 30 min (+ workflow_run)
    "judge-evals.yml": 204,  # Mon 7am ET weekly (drift canary)
    "failure-mode-evals.yml": 204,  # Wed 7am ET weekly
    "verifier-evals.yml": 204,  # Mon 7am ET weekly
    "claim-verify-evals.yml": 204,  # Mon 7am ET weekly
    "dream.yml": 204,  # Sun 3am ET weekly (memory loop)
    "ledger-update.yml": 28,  # daily 6:30am ET (graduation ladder)
    "metrics-digest.yml": 204,  # Mon 8:30am ET weekly
    "release-intelligence.yml": 10,  # cron every 6h (poll + release watchdog)
    "dependabot-triage.yml": 10,  # cron every 6h (Dependabot PR classify/merge/label)
    # on demand — failure check only
    "spec-draft.yml": None,
    "implement.yml": None,
    "code-judge.yml": None,
    "revise.yml": None,
    "claim-verify.yml": None,
}


def fetch_runs(repo: str, token: str, workflow_file: str):
    """Live GitHub API call — the one non-pure piece, kept separate so the
    evaluation logic below can be tested without a network call. Returns
    the workflow_runs list, or {"error": str} on any failure."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/runs"
        "?status=completed&per_page=20",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)["workflow_runs"]
    except Exception as e:
        return {"error": str(e)}


def pause_gated(workflows_dir: Path, wf: str) -> bool:
    """True when the workflow gates its job on AGENT_OPS_PAUSED. Read from
    the checked-out file rather than a hand-kept list here, so this stays
    right as workflows are added or ungated."""
    try:
        return "AGENT_OPS_PAUSED" in (workflows_dir / wf).read_text(encoding="utf-8")
    except OSError as e:
        print(f"::warning::could not read {wf} to check pause gating ({e}) — checking it anyway")
        return False


def evaluate_runs(wf: str, max_age: int | None, runs, now: datetime) -> tuple[list[str], list[str]]:
    """Staleness + latest-run-failed check for one workflow's fetched runs
    (or the {"error": ...} sentinel from fetch_runs). Returns (problems,
    warnings)."""
    if isinstance(runs, dict) and "error" in runs:
        return [], [f"`{wf}`: could not read run history ({runs['error']})"]
    if not runs:
        if max_age is None:
            return [], []
        return [f"`{wf}`: no completed runs found at all"], []

    problems = []
    latest = runs[0]
    if latest["conclusion"] not in ("success", "skipped"):
        problems.append(f"`{wf}`: latest run concluded *{latest['conclusion']}* — {latest['html_url']}")
    if max_age is None:
        return problems, []

    success = next((r for r in runs if r["conclusion"] == "success"), None)
    if success is None:
        problems.append(f"`{wf}`: no successful run in the last {len(runs)} completed runs")
        return problems, []

    age_h = (now - datetime.fromisoformat(success["created_at"].replace("Z", "+00:00"))).total_seconds() / 3600
    if age_h > max_age:
        problems.append(
            f"`{wf}`: last successful run was {age_h:.0f}h ago (window: {max_age}h) — "
            "schedule may have silently stopped"
        )
    return problems, []


def evaluate(
    *,
    now: datetime,
    skip: set[str],
    paused: bool,
    workflows_dir: Path,
    fetch_fn: Callable[[str], object],
    monitored: dict[str, int | None] = MONITORED,
) -> tuple[list[str], list[str], list[str], int]:
    """Decision function over lazily-fetched run data — fetch_fn is called
    only for workflows actually being checked (mirrors the original: a
    paused, pause-gated workflow's run history is never fetched at all).
    Returns (problems, warnings, paused_skips, checked)."""
    problems: list[str] = []
    warnings: list[str] = []
    paused_skips: list[str] = []
    checked = 0

    for wf, max_age in monitored.items():
        if wf in skip:
            continue
        if paused and pause_gated(workflows_dir, wf):
            paused_skips.append(wf)
            continue
        checked += 1
        p, w = evaluate_runs(wf, max_age, fetch_fn(wf), now)
        problems += p
        warnings += w

    return problems, warnings, paused_skips, checked


def render(repo: str, problems: list[str], warnings: list[str], skip: set[str], paused_skips: list[str]) -> str:
    lines = [f"*Pipeline heartbeat — {repo}*"]
    if problems:
        lines += ["", "*Problems:*"] + [f"• {p}" for p in problems]
    if warnings:
        lines += ["", "*Warnings:*"] + [f"• {w}" for w in warnings]
    if skip:
        lines += ["", f"_Muted checks (HEARTBEAT_SKIP): {', '.join(sorted(skip))}_"]
    if paused_skips:
        lines += [
            "",
            f"_Pipeline paused (AGENT_OPS_PAUSED=true) — {len(paused_skips)} gated check(s) not evaluated: "
            f"{', '.join(sorted(paused_skips))}_",
        ]
    return "\n".join(lines)


def post_alert(text: str) -> None:
    # Delegates to the one canonical implementation (echoes to the log
    # itself, degrades to log-only when SLACK_BOT_TOKEN is unset, and posts
    # to ${SLACK_OPS_CHANNEL_ID}) instead of reimplementing the chat.postMessage call.
    subprocess.run(["bash", "scripts/slack-alert.sh", text], check=False)


def main() -> int:
    repo = os.environ["REPO"]
    token = os.environ["GH_TOKEN"]
    skip = {s.strip() for s in os.environ.get("HEARTBEAT_SKIP", "").split(",") if s.strip()}
    paused = os.environ.get("AGENT_OPS_PAUSED", "").strip().lower() == "true"
    now = datetime.now(timezone.utc)

    problems, warnings, paused_skips, checked = evaluate(
        now=now,
        skip=skip,
        paused=paused,
        workflows_dir=Path(".github/workflows"),
        fetch_fn=lambda wf: fetch_runs(repo, token, wf),
    )

    if paused_skips:
        print(
            f"AGENT_OPS_PAUSED=true — skipped {len(paused_skips)} pause-gated check(s): "
            f"{', '.join(sorted(paused_skips))}"
        )

    if not problems and not warnings:
        if checked:
            print(f"Heartbeat healthy — {checked} monitored workflow(s) within their windows.")
        else:
            print("Nothing checked — every monitored workflow is muted or pause-gated.")
        return 0

    text = render(repo, problems, warnings, skip, paused_skips)
    print(text)
    post_alert(text)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
