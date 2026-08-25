#!/usr/bin/env python3
"""Golden-set eval harness for the sales-ops judge agents.

Regression-tests the qualifier-critic and copy-evaluator gates: known-good
fixture leads/drafts run through the UNMODIFIED production agent prompts in a
sandbox directory, and the resulting verdicts are compared against expected
decisions. A decision flip means the judge drifted (rubric edit, prompt edit,
or model change) and the run fails.

Usage:
  run_eval.py setup   --judge {qualifier-critic,copy-evaluator} --sandbox DIR
  run_eval.py compare --judge {qualifier-critic,copy-evaluator} --sandbox DIR

Between setup and compare, the caller runs the judge from inside the sandbox:
  cd $SANDBOX && claude -p "$(cat $REPO/agents/<judge>/CLAUDE.md)" ...

Fixture files may contain {{TODAY}} and {{DAYS_AGO_N}} placeholders, which
setup materializes as ISO dates relative to the run date so that
freshness-sensitive rubric criteria never go stale.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVALS = REPO / "evals"


def materialize_dates(text: str) -> str:
    text = text.replace("{{TODAY}}", date.today().isoformat())
    return re.sub(
        r"\{\{DAYS_AGO_(\d+)\}\}",
        lambda m: (date.today() - timedelta(days=int(m.group(1)))).isoformat(),
        text,
    )


def copy_internal_docs(sandbox: Path) -> None:
    src = REPO / "internal-docs"
    if not src.is_dir():
        sys.exit("internal-docs/ not found in repo root — the workflow must sparse-checkout internal-docs first.")
    shutil.copytree(src, sandbox / "internal-docs", ignore=shutil.ignore_patterns(".git", "node_modules"))


def setup_qualifier_critic(sandbox: Path) -> None:
    (sandbox / "leads/enriched").mkdir(parents=True)
    (sandbox / "leads/critic").mkdir(parents=True)
    copy_internal_docs(sandbox)
    leads = materialize_dates((EVALS / "qualifier-critic/golden-leads.json").read_text())
    (sandbox / "leads/enriched/golden.json").write_text(leads)
    print(f"qualifier-critic sandbox ready: {sandbox} ({len(json.loads(leads))} golden leads)")


def setup_copy_evaluator(sandbox: Path) -> None:
    for d in ("leads/enriched", "sends/queue", "sends/linkedin", "sends/verdicts"):
        (sandbox / d).mkdir(parents=True)
        (sandbox / d / ".gitkeep").touch()
    copy_internal_docs(sandbox)
    leads = materialize_dates((EVALS / "copy-evaluator/golden-leads.json").read_text())
    (sandbox / "leads/enriched/golden.json").write_text(leads)

    # The evaluator identifies "this batch" via `git status --porcelain sends/`,
    # so the sandbox must be a git repo with the drafts left uncommitted.
    def git(*args):
        subprocess.run(["git", *args], cwd=sandbox, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.name", "eval-harness")
    git("config", "user.email", "eval@example.com")
    git("add", "-A")
    git("commit", "-qm", "eval baseline")

    n = 0
    for fixture in sorted((EVALS / "copy-evaluator/golden-drafts").glob("*.json")):
        draft = json.loads(materialize_dates(fixture.read_text()))
        name = f"{date.today().isoformat()}-{draft['lead_id']}-touch{draft['touch_number']}.json"
        (sandbox / "sends/queue" / name).write_text(json.dumps(draft, indent=2))
        n += 1
    print(f"copy-evaluator sandbox ready: {sandbox} ({n} uncommitted golden drafts)")


def load_verdicts(verdict_dir: Path) -> dict:
    verdicts = {}
    for f in sorted(verdict_dir.glob("*.json")):
        for v in json.loads(f.read_text()):
            verdicts[v["lead_email"].lower()] = v
    return verdicts


def codes_match(expected_codes: list, verdict: dict) -> bool:
    actual = [str(c) for c in verdict.get("failing_criteria", []) + verdict.get("disqualifier_hits", []) + verdict.get("hard_block_hits", [])]
    return any(a.upper().startswith(code.upper()) for code in expected_codes for a in actual)


def compare(judge: str, sandbox: Path) -> int:
    verdict_dir = sandbox / ("leads/critic" if judge == "qualifier-critic" else "sends/verdicts")
    expected = json.loads((EVALS / judge / "expected.json").read_text())
    verdicts = load_verdicts(verdict_dir)

    rows, failures = [], 0
    for exp in expected:
        email = exp["lead_email"].lower()
        v = verdicts.get(email)
        if v is None:
            rows.append((email, exp["expected_decision"], "MISSING", "-", "FLIP"))
            failures += 1
            continue
        decision_ok = v.get("decision") == exp["expected_decision"]
        codes_ok = codes_match(exp["expected_codes_any"], v) if exp.get("expected_codes_any") else True
        if not (decision_ok and codes_ok):
            failures += 1
        status = "ok" if (decision_ok and codes_ok) else ("FLIP" if not decision_ok else "CODE MISMATCH")
        rows.append((email, exp["expected_decision"], v.get("decision", "?"), str(v.get("normalized_score", "-")), status))

    header = f"## {judge} golden-set eval — {'FAIL' if failures else 'PASS'} ({len(expected) - failures}/{len(expected)})"
    table = ["| lead | expected | actual | score | status |", "|---|---|---|---|---|"]
    table += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |" for r in rows]
    report = header + "\n\n" + "\n".join(table) + "\n"
    print(report)

    import os
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(report + "\n")

    if failures:
        print(f"{failures} verdict(s) diverged from the golden set. If a fixture is legitimately outdated, update evals/{judge}/ in the same PR as the rubric/prompt change — with a note on why.")
    return 1 if failures else 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["setup", "compare"])
    p.add_argument("--judge", required=True, choices=["qualifier-critic", "copy-evaluator"])
    p.add_argument("--sandbox", required=True, type=Path)
    args = p.parse_args()

    if args.command == "setup":
        if args.sandbox.exists():
            shutil.rmtree(args.sandbox)
        args.sandbox.mkdir(parents=True)
        (setup_qualifier_critic if args.judge == "qualifier-critic" else setup_copy_evaluator)(args.sandbox)
        return 0
    return compare(args.judge, args.sandbox)


if __name__ == "__main__":
    sys.exit(main())
