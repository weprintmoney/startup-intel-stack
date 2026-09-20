"""Deliverability monitor: MXToolbox blacklist check + Google Postmaster
Tools complaint-rate hard-stop.

Extracted from deliverability-monitor.yml's 103-line inline heredoc.
Behavior-preserving, stub and all: the Postmaster Tools complaint-rate
check has never had its ADC/JWT auth wired up, so `complaint_rate` is
always 0.0 today — this extraction does not fix that, only relocates the
existing (acknowledged-incomplete) logic. Uses lib.slack.post instead of
its own inline urllib POST.
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slack import post as slack_post  # noqa: E402

# Slack user ID and channel to alert on hard-stop. Set via env or
# company-profile.yaml channels.slack_webhook_secret notification routing.
ALERT_UID = os.environ.get("DELIVERABILITY_ALERT_UID", "")
ALERT_CHANNEL = os.environ.get("DELIVERABILITY_ALERT_CHANNEL", "#leadership")
try:
    import config as _config
    SENDING_DOMAIN = os.environ.get("SENDING_DOMAIN") or _config.get("company.send_domain", "mail.example.com")
except Exception:
    SENDING_DOMAIN = os.environ.get("SENDING_DOMAIN", "mail.example.com")


def set_repo_variable(name: str, value: str) -> None:
    gh_token = os.environ.get("GH_TOKEN", "")
    repo = os.environ.get("REPO", "")
    if not gh_token or not repo:
        return
    payload = json.dumps({"name": name, "value": value}).encode()
    url = f"https://api.github.com/repos/{repo}/actions/variables/{name}"
    req = urllib.request.Request(
        url,
        data=payload,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {gh_token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Repo variable update error: {e}")


def check_blacklist(sending_domain: str = SENDING_DOMAIN) -> bool:
    """Returns True if the domain is clean. Posts to ALERT_CHANNEL if not."""
    try:
        url = f"https://api.mxtoolbox.com/api/v1/lookup/blacklist/{sending_domain}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        failed = data.get("Failed", [])
        if not failed:
            return True
        print(f"Blacklist hits: {failed}")
        slack_post(
            ALERT_CHANNEL,
            f":rotating_light: *{sending_domain} is blacklisted* on {len(failed)} provider(s): "
            + ", ".join(f.get("Name", "?") for f in failed),
        )
        return False
    except Exception as e:
        print(f"MXToolbox check skipped (no API key or error): {e}")
        return True


def check_postmaster_complaint_rate() -> float:
    """Google Postmaster Tools complaint rate. Stub: the real API call
    requires ADC/JWT auth that was never wired up, so this always returns
    0.0 when credentials are present — same as the original inline code."""
    gcp_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not gcp_creds:
        return 0.0
    try:
        json.loads(gcp_creds)  # validate the credential blob parses
        print("Google Postmaster Tools: credentials present, ADC/JWT auth required at runtime.")
    except Exception as e:
        print(f"Postmaster Tools error: {e}")
    return 0.0


def evaluate_and_act(complaint_rate: float, dns_ok: bool) -> int:
    """Thresholds: >0.3% hard-stops (exit 1), >0.1% pauses (exit 0),
    otherwise healthy. Returns the process exit code."""
    if complaint_rate > 0.003:
        print(f"CRITICAL: complaint rate {complaint_rate:.1%} — hard stop")
        set_repo_variable("SEQUENCES_PAUSED", "true")
        slack_post(
            ALERT_CHANNEL,
            f":red_circle: *HARD STOP* — complaint rate {complaint_rate:.1%} exceeds 0.3%. "
            "`SEQUENCES_PAUSED` set to true.",
        )
        slack_post(
            ALERT_UID,
            f":rotating_light: Outreach hard-stopped. Complaint rate: {complaint_rate:.1%}. Review immediately.",
        )
        return 1
    if complaint_rate > 0.001:
        print(f"WARNING: complaint rate {complaint_rate:.1%} — pausing sequences")
        set_repo_variable("SEQUENCES_PAUSED", "true")
        slack_post(
            ALERT_CHANNEL,
            f":warning: Complaint rate {complaint_rate:.1%} exceeds 0.1% threshold. "
            "`SEQUENCES_PAUSED` set to true until reviewed.",
        )
        return 0
    print(f"Deliverability OK. Complaint rate: {complaint_rate:.3%}. DNS: {'OK' if dns_ok else 'CHECK BLACKLISTS'}")
    return 0


def main() -> int:
    dns_ok = check_blacklist()
    complaint_rate = check_postmaster_complaint_rate()
    return evaluate_and_act(complaint_rate, dns_ok)


if __name__ == "__main__":
    sys.exit(main())
