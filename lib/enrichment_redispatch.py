"""Enrichment re-dispatch decision: count remaining work, decide handoff vs
continue, re-dispatch enrichment.yml when there's more to do.

Extracted from enrichment.yml's "Re-dispatch if work remains" step
(previously a 96-line inline `python3 - <<'PYEOF'` heredoc). Behavior is
unchanged; the hand-rolled suppression-set builder is replaced by
suppression.suppressed_sets().
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suppression import suppressed_sets  # noqa: E402

SIGNALS = (
    "pain_points",
    "event_date",
    "funding_date",
    "hiring_signal",
    "product_launch_date",
    "rfp_status",
)


def _load(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        print(f"WARNING: unreadable, treating as empty: {path} ({exc})")
        return []
    return data if isinstance(data, list) else [data]


def _lead_key(rec: dict) -> tuple[str, str]:
    return (
        (rec.get("contact_name") or "").strip().lower(),
        (rec.get("company_name") or "").strip().lower(),
    )


def count_remaining_signal_refresh(enriched_dir: Path) -> int:
    """Deliverable, non-suppressed, not-yet-duplicate leads missing every
    research signal and not already marked checked."""
    sup_emails, sup_domains = suppressed_sets()
    seen: set[str] = set()
    remaining = 0
    for f in enriched_dir.glob("*.json"):
        for lead in _load(f):
            email = (lead.get("email") or "").lower()
            if not email or lead.get("email_status") != "deliverable":
                continue
            if email in seen or email in sup_emails:
                continue
            if email.split("@")[-1] in sup_domains:
                continue
            seen.add(email)
            if not any(k in lead for k in SIGNALS) and "signals_checked" not in lead:
                remaining += 1
    return remaining


def count_remaining_normal(enriched_dir: Path, pre_filtered_dir: Path) -> int:
    """Pre-filtered leads (identity: contact_name + company_name, the same
    key dedup.yml matches on) not yet present in leads/enriched/."""
    enriched_keys = set()
    for f in enriched_dir.glob("*.json"):
        enriched_keys.update(_lead_key(r) for r in _load(f))

    remaining = 0
    for p in sorted(pre_filtered_dir.glob("*.json")):
        # *-rejects.json failed the ICP gate and is never enriched; counting
        # it kept `remaining` permanently above zero.
        if p.stem.endswith("-rejects"):
            continue
        todo = sum(1 for r in _load(p) if _lead_key(r) not in enriched_keys)
        if todo:
            print(f"  {p.name}: {todo} lead(s) not yet enriched")
        remaining += todo
    return remaining


def decide(remaining: int, committed: bool) -> bool:
    """True = hand off downstream now. False = re-dispatch to continue.

    Hand off when everything is enriched, or when this pass produced
    nothing new (whatever is left is unenrichable — e.g. competitor-
    suppressed leads the agent skips without writing a record).
    """
    return remaining == 0 or not committed


def main() -> int:
    signal_refresh = os.environ.get("SIGNAL_REFRESH") == "true"
    committed = os.environ.get("COMMITTED") == "true"

    if signal_refresh:
        remaining = count_remaining_signal_refresh(Path("leads/enriched"))
    else:
        remaining = count_remaining_normal(Path("leads/enriched"), Path("leads/pre-filtered"))

    print(f"remaining work items: {remaining} (committed this pass: {committed})")
    handoff = decide(remaining, committed)
    if remaining > 0 and not committed:
        print("no progress this pass; not re-dispatching, handing off instead")

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"remaining={remaining}\n")
            f.write(f"handoff={'true' if handoff else 'false'}\n")

    if remaining > 0 and committed:
        args = [
            "gh", "workflow", "run", "enrichment.yml",
            "--repo", os.environ["GITHUB_REPOSITORY"], "--ref", "main",
        ]
        if signal_refresh:
            args += ["-f", "signal_refresh=true"]
        if os.environ.get("RETRY_NOT_FOUND") == "true":
            args += ["-f", "retry_not_found=true"]
        subprocess.run(args, check=True)
        print("re-dispatched enrichment to continue")

    return 0


if __name__ == "__main__":
    sys.exit(main())
