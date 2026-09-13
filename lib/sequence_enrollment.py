"""Copy-evaluator gate: move failed drafts out of the send queue.

Extracted from sequence-enrollment.yml's "Move failed drafts out of the
queue" heredoc (the workflow's only inline Python step — the rest is
Claude Code agent invocations, left untouched). Behavior-preserving:
same fail-closed semantics (a missing verdicts file, or any unverdicted
email draft, kills the run before a PR opens), same rejected-drafts
move, same PR body table.

LinkedIn drafts (sends/linkedin/) are exempt from copy-evaluator
scoring — they're manual 300-char connect notes a human sends
themselves — and are never fail-closed for a missing verdict.
"""

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

PR_BODY_PATH = Path("/tmp/pr-body.md")


def verdicts_path(today_utc: str) -> Path:
    return Path(f"sends/verdicts/{today_utc}.json")


def load_verdicts(vfile: Path) -> list[dict] | None:
    if not vfile.exists():
        print(f"FAIL-CLOSED: {vfile} not found — evaluator produced no verdicts; refusing to open an ungated PR.")
        return None
    return json.loads(vfile.read_text())


def failed_lead_ids(verdicts: list[dict]) -> set[str]:
    return {v["lead_id"] for v in verdicts if v.get("decision") != "PASS" and v.get("lead_id")}


def move_failed_drafts(dirs: list[Path], failed_ids: set[str], rejected_dir: Path) -> int:
    moved = 0
    for d in dirs:
        if not d.exists():
            continue
        for f in list(d.glob("*.json")):
            try:
                lead_id = json.loads(f.read_text()).get("lead_id", "")
            except Exception:
                continue
            if lead_id in failed_ids:
                rejected_dir.mkdir(parents=True, exist_ok=True)
                f.rename(rejected_dir / f.name)
                moved += 1
    return moved


def unverdicted_email_leads(queue_dir: Path, scored_ids: set) -> list[str]:
    unverdicted = []
    if queue_dir.exists():
        for f in queue_dir.glob("*.json"):
            try:
                lid = json.loads(f.read_text()).get("lead_id", "")
            except Exception:
                continue
            if lid and lid not in scored_ids:
                unverdicted.append(lid)
    return unverdicted


def build_pr_body(verdicts: list[dict], today: str) -> str:
    rows = []
    for v in sorted(verdicts, key=lambda x: x.get("decision", "")):
        mark = "✅" if v.get("decision") == "PASS" else "❌"
        fails = ", ".join(v.get("failing_criteria", []) + v.get("hard_block_hits", [])) or "—"
        rows.append(
            f"| {mark} {v.get('decision')} | {v.get('lead_email', '')} | "
            f"{v.get('normalized_score', '')}/100 | {fails} |"
        )

    body = f"""## Review before merging

    Each file under `sends/queue/` is one email that WILL BE SENT after
    merge (on its scheduled date, via Resend). Files under `sends/linkedin/`
    are LinkedIn touches for manual sending.

    ## Copy-evaluator verdicts ({today})

    | Verdict | Lead | Score | Failing criteria |
    |---|---|---|---|
    {chr(10).join(rows)}

    FAILed leads' drafts were moved to `sends/rejected/` — they will NOT send.
    To rescue one: fix the copy per the `feedback` field in
    `sends/verdicts/{today}.json`, move the files back to
    `sends/queue/` on this branch, then merge.

    **To approve:** review the copy in the diff, remove any leads you don't
    want (delete their queue files from this branch), then merge.

    **To reject the whole batch:** close this PR.
    """
    return "\n".join(line.lstrip() for line in body.splitlines())


def run(
    *, queue_dir: Path, linkedin_dir: Path, rejected_dir: Path, vfile: Path, today: str, pr_body_path: Path,
) -> int:
    verdicts = load_verdicts(vfile)
    if verdicts is None:
        return 1

    failed_ids = failed_lead_ids(verdicts)
    moved = move_failed_drafts([queue_dir, linkedin_dir], failed_ids, rejected_dir)

    scored_ids = {v.get("lead_id") for v in verdicts}
    unverdicted = unverdicted_email_leads(queue_dir, scored_ids)
    if unverdicted:
        print(f"FAIL-CLOSED: email drafts without verdicts: {sorted(set(unverdicted))}")
        return 1

    print(f"Failed leads: {len(failed_ids)}; draft files moved to sends/rejected/: {moved}")

    pr_body_path.write_text(build_pr_body(verdicts, today))
    return 0


def main() -> int:
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return run(
        queue_dir=Path("sends/queue"),
        linkedin_dir=Path("sends/linkedin"),
        rejected_dir=Path("sends/rejected"),
        vfile=verdicts_path(today_utc),
        today=date.today().isoformat(),
        pr_body_path=PR_BODY_PATH,
    )


if __name__ == "__main__":
    sys.exit(main())
