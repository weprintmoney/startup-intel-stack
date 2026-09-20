"""Pipeline heartbeat: absence-alerting for this repo's scheduled workflows.

GitHub alerts when a workflow RUN fails, but says nothing when a schedule
silently stops firing or a workflow "succeeds" while producing nothing.
This checks:
  1. staleness — no successful run of a monitored workflow within its window
  2. latest completed run of a monitored workflow failed
  3. CRITICAL — emails were sent recently but reply-monitor is stale, which
     means Hard Rule 5 (pause on reply) is not being enforced
  4. weekly-crawl succeeded but leads/raw/ has no fresh output (zero-output)

Silence = healthy.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from slack import post  # noqa: E402

# Channel ID (or Slack user ID for a DM, if SLACK_BOT_TOKEN is set — see
# lib/slack.py) to post heartbeat alerts to.
ALERT_CHANNEL = os.environ.get("HEARTBEAT_ALERT_CHANNEL", "")

# workflow file -> max hours since last successful run.
# Windows are sized so the Tue-Sat 7:30 AM ET check tolerates the weekend
# gap of weekday-only schedules.
MONITORED = {
    "weekly-crawl.yml": 204,           # Mon 8am ET weekly
    "deliverability-monitor.yml": 36,  # daily 7am ET
    "smtp-send.yml": 28,               # hourly 8am-6pm ET M-F
    "reply-monitor.yml": 28,           # hourly 8am-6pm ET M-F
    "dedup-review.yml": 204,           # part of the weekly-crawl chain
}
# Add a judge-evals.yml / evergreen-nurture.yml entry (204h ~ weekly) once
# this repo schedules those workflows — they're intentionally absent
# here so heartbeat never reports a "stale" workflow that doesn't exist yet.
# apify-ingest.yml is likewise absent until its cron is enabled.

# The automated send loop. Monitored only in find-and-draft mode with a
# real email provider; with sending.provider "manual" these workflows are
# permanent no-ops (humans send from the packet + lead issues), so their
# "staleness" would be noise and the sends-without-reply-monitor CRITICAL
# has nothing to enforce.
SEND_PATH_WORKFLOWS = ("deliverability-monitor.yml", "smtp-send.yml", "reply-monitor.yml")


def fetch_runs(repo: str, token: str, workflow_file: str):
    """Live GitHub API call — the one non-pure piece, kept separate so
    `evaluate()` below can be tested without a network call."""
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


def _check_monitored_workflows(
    now: datetime, skip: set[str], runs_by_workflow: dict, monitored: dict[str, int]
) -> tuple[list[str], list[str], float | None]:
    """Staleness + latest-run-failed check. Returns (problems, warnings, reply_monitor_age_h)."""
    problems: list[str] = []
    warnings: list[str] = []
    reply_monitor_age_h = None

    for wf, max_age in monitored.items():
        if wf in skip:
            continue
        rs = runs_by_workflow.get(wf)
        if isinstance(rs, dict) and "error" in rs:
            warnings.append(f"`{wf}`: could not read run history ({rs['error']})")
            continue
        if not rs:
            problems.append(f"`{wf}`: no completed runs found at all")
            continue
        latest = rs[0]
        if latest["conclusion"] not in ("success", "skipped"):
            problems.append(f"`{wf}`: latest run concluded *{latest['conclusion']}* — {latest['html_url']}")
        success = next((r for r in rs if r["conclusion"] == "success"), None)
        if success is None:
            problems.append(f"`{wf}`: no successful run in the last {len(rs)} completed runs")
            continue
        age_h = (now - datetime.fromisoformat(success["created_at"].replace("Z", "+00:00"))).total_seconds() / 3600
        if wf == "reply-monitor.yml":
            reply_monitor_age_h = age_h
        if age_h > max_age:
            problems.append(
                f"`{wf}`: last successful run was {age_h:.0f}h ago (window: {max_age}h) — "
                "schedule may have silently stopped"
            )

    return problems, warnings, reply_monitor_age_h


def _reply_monitor_critical(
    now: datetime,
    skip: set[str],
    in_business_window: bool,
    daily_count: dict | None,
    reply_monitor_age_h: float | None,
    manual: bool = False,
) -> str | None:
    """CRITICAL: sends happened recently but reply-monitor is stale. Reply
    detection is what enforces Hard Rule 5 (pause on reply). In manual
    mode nothing is sent by CI and replies are recorded by the human on the
    lead issue, so there is nothing for this check to enforce."""
    if manual:
        return None
    dc = daily_count or {}
    sent_recently = dc.get("count", 0) > 0 and dc.get("date", "") >= (now - timedelta(days=2)).date().isoformat()
    if not (
        sent_recently
        and "reply-monitor.yml" not in skip
        and in_business_window
        and (reply_monitor_age_h is None or reply_monitor_age_h > 3)
    ):
        return None
    age = "unknown" if reply_monitor_age_h is None else f"{reply_monitor_age_h:.0f}h"
    return (
        f":rotating_light: *CRITICAL*: emails were sent recently (daily count {dc.get('count')} on "
        f"{dc.get('date')}) but reply-monitor's last success was {age} ago. Replies are NOT being "
        "detected — Hard Rule 5 (pause on reply) is not enforced. Consider setting "
        "SEQUENCES_PAUSED=true until it recovers."
    )


def _zero_output_warning(
    now: datetime, skip: set[str], raw_lead_dates: list[str], already_a_problem: bool
) -> str | None:
    """weekly-crawl healthy but no fresh raw leads file."""
    if "weekly-crawl.yml" in skip or not raw_lead_dates or already_a_problem:
        return None
    newest = max(raw_lead_dates)
    if newest >= (now - timedelta(days=9)).date().isoformat():
        return None
    return (
        f"`weekly-crawl.yml`: runs are green but the newest `leads/raw/` file is dated "
        f"{newest} (>9 days). The crawl may be succeeding while producing nothing."
    )


def evaluate(
    *,
    now: datetime,
    skip: set[str],
    in_business_window: bool,
    runs_by_workflow: dict,
    daily_count: dict | None,
    raw_lead_dates: list[str],
    monitored: dict[str, int] = MONITORED,
    manual: bool = False,
) -> tuple[list[str], list[str]]:
    """Pure decision function — no I/O. Returns (problems, warnings)."""
    problems, warnings, reply_monitor_age_h = _check_monitored_workflows(now, skip, runs_by_workflow, monitored)

    critical = _reply_monitor_critical(
        now, skip, in_business_window, daily_count, reply_monitor_age_h, manual=manual
    )
    if critical:
        problems.insert(0, critical)

    zero_output = _zero_output_warning(
        now, skip, raw_lead_dates, already_a_problem=any("weekly-crawl.yml" in p for p in problems)
    )
    if zero_output:
        warnings.append(zero_output)

    return problems, warnings


def render(repo: str, problems: list[str], warnings: list[str], skip: set[str]) -> str:
    lines = [f"*Pipeline heartbeat — {repo}*"]
    if problems:
        lines += ["", "*Problems:*"] + [f"• {p}" for p in problems]
    if warnings:
        lines += ["", "*Warnings:*"] + [f"• {w}" for w in warnings]
    if skip:
        lines += ["", f"_Muted checks (HEARTBEAT_SKIP): {', '.join(sorted(skip))}_"]
    return "\n".join(lines)


def _raw_lead_dates(raw_dir: Path) -> list[str]:
    dates = []
    for f in raw_dir.glob("*.json"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
        if m:
            dates.append(m.group(1))
    return dates


def _monitored_for_stage(stage: str, provider: str = "resend") -> dict[str, int]:
    """find-and-draft (legacy alias: series-a) unlocks the full outbound-send
    loop; below that, those workflows are mode-gated no-ops in their own
    preflight and would never show a real "success" run, so staleness would
    just be noise. The same applies when sending.provider is "manual": the
    send-path workflows exit at their provider gate on every run."""
    monitored = {k: v for k, v in MONITORED.items() if k in ("weekly-crawl.yml", "dedup-review.yml")}
    if config.normalize_mode(stage) == "find-and-draft" and provider != config.MANUAL_PROVIDER:
        monitored.update({k: v for k, v in MONITORED.items() if k in SEND_PATH_WORKFLOWS})
    return monitored


def main() -> int:
    repo = os.environ["REPO"]
    token = os.environ["GH_TOKEN"]
    stage = os.environ.get("STAGE", "seed")
    provider = (os.environ.get("SENDING_PROVIDER") or "resend").strip().lower()
    manual = provider == config.MANUAL_PROVIDER
    skip = {s.strip() for s in os.environ.get("HEARTBEAT_SKIP", "").split(",") if s.strip()}
    now = datetime.now(timezone.utc)
    try:
        local_now = now.astimezone(ZoneInfo(os.environ.get("HQ_TZ", "UTC")))
    except Exception:
        local_now = now
    in_business_window = local_now.weekday() < 5 and 9 <= local_now.hour < 18

    monitored = _monitored_for_stage(stage, provider)
    runs_by_workflow = {wf: fetch_runs(repo, token, wf) for wf in monitored if wf not in skip}

    try:
        daily_count = json.loads(Path("sends/daily-count.json").read_text())
    except Exception:
        daily_count = None

    problems, warnings = evaluate(
        now=now,
        skip=skip,
        in_business_window=in_business_window,
        runs_by_workflow=runs_by_workflow,
        daily_count=daily_count,
        raw_lead_dates=_raw_lead_dates(Path("leads/raw")),
        monitored=monitored,
        manual=manual,
    )

    if not problems and not warnings:
        print("Heartbeat healthy — all monitored workflows within their windows.")
        return 0

    text = render(repo, problems, warnings, skip)
    print(text)
    post(ALERT_CHANNEL, text)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
