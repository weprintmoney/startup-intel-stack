"""Email warmup fallback (manual-trigger only).

Extracted from warmup.yml's 95-line inline heredoc. Behavior-preserving:
same day-number-from-log-count derivation, same 20/40/50 daily-cap ramp,
same self-terminate-after-day-28 behavior, same log shape.

Decision 2026-07-15: warm-up happens through low-volume real sends
(sequence-enrollment with max_leads 10-15), not seed addresses. This is
kept as a fallback, dispatched manually.
"""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import requests

RESEND_URL = "https://api.resend.com/emails"


def day_number(log_dir: Path) -> int:
    return len(sorted(log_dir.glob("*.json"))) + 1


def daily_cap_for_day(day: int) -> int:
    if day <= 7:
        return 20
    if day <= 14:
        return 40
    return 50


def set_warmup_complete(repo: str, *, check: bool) -> None:
    subprocess.run(
        [
            "gh", "api",
            f"repos/{repo}/actions/variables/WARMUP_COMPLETE",
            "-X", "PATCH", "-f", "name=WARMUP_COMPLETE", "-f", "value=true",
        ],
        check=check,
    )


def send_warmup_batch(
    seed_addresses: list[str], day: int, cap: int, api_key: str, from_address: str,
    *, sender_name: str, company_name: str,
) -> list[dict]:
    results = []
    for addr in seed_addresses[:cap]:
        payload = {
            "from": f"{sender_name} <{from_address}>",
            "to": [addr],
            "subject": f"{company_name} warmup — day {day}",
            "text": f"This is a warmup email from {company_name} outreach (day {day}). Please do not reply.",
        }
        try:
            resp = requests.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            ok = resp.status_code == 200
            results.append({"to": addr, "success": ok, "error": None if ok else resp.text})
        except Exception as e:
            results.append({"to": addr, "success": False, "error": str(e)})
    return results


def run(
    log_dir: Path, *, seed_addresses: list[str], api_key: str, from_address: str, repo: str, today: str,
    sender_name: str, company_name: str,
) -> int:
    day = day_number(log_dir)
    print(f"Warmup day {day}")

    if day > 28:
        print("Warmup complete (day 28 passed). Setting WARMUP_COMPLETE=true.")
        set_warmup_complete(repo, check=True)
        return 0

    cap = daily_cap_for_day(day)

    if not seed_addresses:
        print("No seed addresses configured. Skipping.")
        return 0

    results = send_warmup_batch(
        seed_addresses, day, cap, api_key, from_address,
        sender_name=sender_name, company_name=company_name,
    )
    sent = sum(1 for r in results if r["success"])

    log_path = log_dir / f"{today}.json"
    log_path.write_text(json.dumps(
        {"date": today, "day_number": day, "daily_cap": cap, "sent": sent, "results": results}, indent=2,
    ))
    print(f"Sent {sent}/{cap} warmup emails. Log: {log_path}")

    if day == 28:
        print("Day 28 complete. Setting WARMUP_COMPLETE=true.")
        set_warmup_complete(repo, check=False)

    return 0


def main() -> int:
    import config
    seed_addresses = [a.strip() for a in os.environ.get("WARMUP_SEED_ADDRESSES", "").split(",") if a.strip()]
    return run(
        Path("warmup/log"),
        seed_addresses=seed_addresses,
        api_key=os.environ["RESEND_API_KEY"],
        from_address=os.environ.get("RESEND_FROM", f"outreach@{config.get('company.send_domain', 'mail.example.com')}"),
        repo=os.environ["REPO"],
        today=date.today().isoformat(),
        sender_name=os.environ.get("WARMUP_SENDER_NAME", f"{config.get('company.name', 'Outreach')} Outreach"),
        company_name=config.get("company.name", "Outreach"),
    )


if __name__ == "__main__":
    sys.exit(main())
