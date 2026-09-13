"""
Outcome-level pass/fail logic for dedup-review.yml's CRM upsert step.

On 2026-09-06 dedup-review.yml exited 0 while 24 of 24 CRM upserts failed
(`value_not_found: pre-seed`) — the step asserted nothing about outcome, only
that the script didn't crash. This module makes outcome checkable:
`classify()` sorts an upsert exception into an infra gap (the CRM People
schema isn't provisioned yet — expected until the CRM schema is provisioned) or a real
error; `decide()` turns a run summary into failure reasons (empty = pass);
`render_markdown()` renders the same summary for the job's step summary.
"""

from __future__ import annotations

SCHEMA_UNPROVISIONED_MARKERS = ("Cannot find attribute", "not authorized")


def classify(msg: str) -> str:
    """Sort an CRM upsert exception message into a known bucket.

    `schema_unprovisioned`: the People object is missing a custom attribute
    — an infra gap (the CRM schema needs provisioning), not a code bug, so it never
    counts toward `attempted`. Everything else is `crm_error` — a real
    outcome failure (bad select-option value, rate limit, etc.).
    """
    return "schema_unprovisioned" if any(m in msg for m in SCHEMA_UNPROVISIONED_MARKERS) else "crm_error"


def new_summary() -> dict:
    """An empty run summary with the shape dedup-review.yml fills in."""
    return {
        "verdict_pass": 0,
        "attempted": 0,
        "upserted": 0,
        "readback_ok": 0,
        "readback_mismatch": 0,
        "skipped": {
            "no_email": 0,
            "suppressed": 0,
            "critic_fail": 0,
            "prior_contact": 0,
            "schema_unprovisioned": 0,
        },
        "escalated": 0,
        "errors": {"crm_error": 0},
        "error_lines": [],
    }


def decide(summary: dict) -> list[str]:
    """Failure reasons for this run. Empty list = the step should exit 0.

    A schema-unprovisioned-only run (every attempt hit the infra gap, none
    counted toward `attempted`) stays green — that's an expected pre-#45
    state, not an outcome failure. Anything that got a real attempt and
    still didn't land — zero upserts landing, a mismatched read-back, or a
    non-schema CRM error — fails loud.
    """
    reasons = []
    if summary["attempted"] > 0 and summary["upserted"] == 0:
        reasons.append(f"{summary['attempted']} upsert(s) attempted, 0 landed")
    if summary["readback_mismatch"] > 0:
        reasons.append(
            f"{summary['readback_mismatch']} read-back mismatch(es) — "
            "CRM holds different values than we wrote"
        )
    if summary["errors"]["crm_error"] > 0:
        reasons.append(
            f"{summary['errors']['crm_error']} CRM error(s) outside the schema-unprovisioned gap"
        )
    return reasons


def render_markdown(summary: dict) -> str:
    """Render `summary` as the dedup-review.yml step summary."""
    reasons = decide(summary)
    verdict = "FAIL" if reasons else "PASS"
    other_skipped = sum(v for k, v in summary["skipped"].items() if k != "schema_unprovisioned")

    lines = [
        f"## CRM upsert — {verdict}",
        "",
        "| | |",
        "|---|---|",
        f"| PASS verdicts seen | {summary['verdict_pass']} |",
        f"| Upsert attempted | {summary['attempted']} |",
        f"| Upserted | {summary['upserted']} |",
        f"| Read-back OK | {summary['readback_ok']} |",
        f"| Read-back mismatch | {summary['readback_mismatch']} |",
        f"| Escalated (no verdict / ESCALATE) | {summary['escalated']} |",
        f"| Skipped — schema unprovisioned | {summary['skipped']['schema_unprovisioned']} |",
        f"| Skipped — other | {other_skipped} |",
        f"| CRM errors | {summary['errors']['crm_error']} |",
    ]
    if reasons:
        lines += ["", "**Failure reasons:**"] + [f"- {r}" for r in reasons]
    if summary["error_lines"]:
        lines += ["", "**First error lines:**"] + [f"- `{e}`" for e in summary["error_lines"][:3]]
    return "\n".join(lines) + "\n"
