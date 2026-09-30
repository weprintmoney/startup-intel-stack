#!/usr/bin/env python3
"""Golden-set runner for the claim-verify gate (scripts/verify-claims.py +
agents/claim-verifier/).

Fixtures live in evals/claim-verify-cases/<slug>/ (case.json + artifact);
shared synthetic sources in evals/claim-verify-cases/_fixtures/.

Two modes:

  deterministic [--only a,b]
      No model, no API key. For every case: materialize sources, run
      `extract`, and assert the pre-pass alone catches every
      `expected_deterministic` claim with the right verdict, and produces
      no contradicted/unverified claims on clean cases. Exit 1 on any miss.

  cases / setup / collect / compare   (driven by claim-verify-evals.yml)
      run-claim-verify-evals.py cases [--only a,b]
      run-claim-verify-evals.py setup   --case SLUG
      <workflow runs: claude -p agents/claim-verifier/CLAUDE.md ...>
      run-claim-verify-evals.py collect --case SLUG --results DIR
      run-claim-verify-evals.py compare --results DIR [--only a,b]

`setup` materializes /tmp/claim-verify/ exactly as production does (artifact,
sources/, claims.json, run-meta.json) against the _fixtures trees, so the
production prompt runs unmodified. `compare` runs `aggregate` on the
collected model verdict and asserts:

- final verdict == case.expected_verdict
- every expected_claims entry with a non-verified verdict is matched by a
  final claim with that verdict sharing a distinctive token (word >=5 chars
  or a number — same forgiving rule as run-verifier-evals.py)
- clean cases (expected verified) have zero contradicted/unverified claims
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CASES_DIR = REPO / "evals" / "claim-verify-cases"
FIXTURES = CASES_DIR / "_fixtures"
WORK = Path("/tmp/claim-verify")
VERIFY = REPO / "scripts" / "verify-claims.py"


def list_cases(only: str | None) -> list[str]:
    slugs = sorted(d.name for d in CASES_DIR.iterdir()
                   if d.is_dir() and (d / "case.json").is_file())
    if only:
        wanted = [s.strip() for s in only.split(",") if s.strip()]
        missing = [w for w in wanted if w not in slugs]
        if missing:
            sys.exit(f"unknown case(s): {', '.join(missing)}")
        slugs = wanted
    return slugs


def load_case(slug: str) -> dict:
    return json.loads((CASES_DIR / slug / "case.json").read_text())


def _run(args: list[str]) -> None:
    subprocess.run([sys.executable, str(VERIFY), *args], check=True)


def materialize(slug: str, work: Path = WORK) -> dict:
    """Build the production input layout for one case under `work`."""
    case = load_case(slug)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    artifact_src = CASES_DIR / slug / case["artifact"]
    artifact_dst = work / ("artifact.md" if case["kind"] == "spec" else "artifact.json")
    shutil.copy(artifact_src, artifact_dst)
    _run(["sources", "--internal-docs", str(FIXTURES / "internal-docs"),
          "--docs-repo", str(FIXTURES / "docs-public"), "--out", str(work / "sources")])
    extract = ["extract", "--kind", case["kind"], "--artifact", str(artifact_dst),
               "--artifact-ref", case["artifact_ref"], "--sources", str(work / "sources"),
               "--internal-docs", str(FIXTURES / "internal-docs"), "--out", str(work / "claims.json")]
    if case["kind"] == "spec":
        extract += ["--product", str(FIXTURES / "product"), "--agent-ops", str(FIXTURES / "agent-ops")]
    _run(extract)
    (work / "run-meta.json").write_text(json.dumps({
        "artifact_kind": case["kind"],
        "artifact_ref": case["artifact_ref"],
        "run_url": f"https://github.com/example-org/agent-ops/evals/{slug}",
    }, indent=2) + "\n")
    return case


def _tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[A-Za-z0-9_./-]{5,}", text.lower()))
    tokens |= set(re.findall(r"\b\d+\b", text))
    return tokens


def _matches(expected_claim: str, verdict: str, claims: list[dict]) -> bool:
    wanted = _tokens(expected_claim)
    for c in claims:
        if c.get("verdict") != verdict:
            continue
        hay = _tokens(" ".join(str(c.get(k) or "") for k in ("claim", "evidence", "note", "source")))
        if wanted & hay:
            return True
    return False


def _report(title: str, rows: list[tuple], failures: int) -> None:
    header = f"## {title} — {'FAIL' if failures else 'PASS'} ({len(rows) - failures}/{len(rows)})"
    table = ["| case | expected | actual | status |", "|---|---|---|---|"]
    table += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |" for r in rows]
    report = header + "\n\n" + "\n".join(table) + "\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(report + "\n")


# ---------------------------------------------------------- deterministic --

def deterministic(only: str | None) -> int:
    """Pre-pass-only check. Uses a private temp dir, never /tmp/claim-verify,
    so it can run alongside a model eval without clobbering its sandbox."""
    import tempfile
    rows, failures = [], 0
    work = Path(tempfile.mkdtemp(prefix="claim-verify-det-"))
    for slug in list_cases(only):
        case = materialize(slug, work)
        claims = json.loads((work / "claims.json").read_text())["claims"]
        problems = []
        for ed in case.get("expected_deterministic", []):
            if not _matches(ed["claim"], ed["verdict"], claims):
                problems.append(f"pre-pass missed {ed['verdict']}: {ed['claim']!r}")
        if case["expected_verdict"] == "verified":
            for c in claims:
                if c["verdict"] in ("contradicted", "unverified"):
                    problems.append(f"false positive ({c['verdict']}): {c['claim'][:80]!r}")
        settled = sum(1 for c in claims if c["verdict"] != "pending")
        pending = sum(1 for c in claims if c["verdict"] == "pending")
        actual = f"{settled} settled / {pending} pending"
        status = "ok" if not problems else "FAIL: " + "; ".join(problems)
        if problems:
            failures += 1
        rows.append((slug, f"{len(case.get('expected_deterministic', []))} planted", actual, status))
    shutil.rmtree(work, ignore_errors=True)
    _report("claim-verify deterministic pre-pass eval", rows, failures)
    return 1 if failures else 0


# ---------------------------------------------------------------- model ----

def setup(slug: str) -> None:
    case = materialize(slug)
    print(f"sandbox ready for {slug} ({case['kind']}): {WORK}")


def collect(slug: str, results: Path) -> None:
    dest = results / slug
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(WORK / "claims.json", dest / "claims.json")
    src = WORK / "verdict.json"
    if src.is_file():
        shutil.copy(src, dest / "verdict.json")
    else:
        print(f"::warning::{slug}: no verifier output at {src}")


def compare(results: Path, only: str | None) -> int:  # noqa: C901 — pre-existing, not a lint-floor refactor
    rows, failures = [], 0
    for slug in list_cases(only):
        case = load_case(slug)
        cdir = results / slug
        if not (cdir / "claims.json").is_file():
            rows.append((slug, case["expected_verdict"], "MISSING", "FAIL: no claims.json collected"))
            failures += 1
            continue
        final_path = cdir / "final.json"
        args = ["aggregate", "--claims", str(cdir / "claims.json"),
                "--run-url", f"https://github.com/example-org/agent-ops/evals/{slug}",
                "--out", str(final_path), "--md", str(cdir / "final.md")]
        if (cdir / "verdict.json").is_file():
            args += ["--model-verdict", str(cdir / "verdict.json")]
        try:
            _run(args)
            final = json.loads(final_path.read_text())
        except Exception as e:  # noqa: BLE001
            rows.append((slug, case["expected_verdict"], "UNPARSEABLE", f"FAIL: {e}"))
            failures += 1
            continue

        problems = []
        if final["verdict"] != case["expected_verdict"]:
            problems.append(f"verdict {final['verdict']} != {case['expected_verdict']}")
        for ec in case.get("expected_claims", []):
            if ec["expected_verdict"] == "verified":
                continue
            if not _matches(ec["claim"], ec["expected_verdict"], final["claims"]):
                problems.append(f"missed {ec['expected_verdict']}: {ec['claim']!r}")
        if case["expected_verdict"] == "verified":
            for c in final["claims"]:
                if c["verdict"] != "verified":
                    problems.append(f"false positive ({c['verdict']}): {c['claim'][:80]!r}")
        status = "ok" if not problems else "FAIL: " + "; ".join(problems)
        if problems:
            failures += 1
        rows.append((slug, case["expected_verdict"], final["verdict"], status))
    _report("claim-verifier golden-set eval", rows, failures)
    if failures:
        print(f"{failures} case(s) failed. Either the verifier prompt / pre-pass drifted or a "
              f"fixture is out of date — the fix goes in the same PR as the change, on a "
              f"`dream/claim-verifier-*` branch for prompt edits.")
    return 1 if failures else 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["cases", "setup", "collect", "compare", "deterministic"])
    p.add_argument("--case")
    p.add_argument("--results", type=Path)
    p.add_argument("--only", help="comma-separated case subset")
    args = p.parse_args()

    if args.command == "cases":
        print("\n".join(list_cases(args.only)))
        return 0
    if args.command == "deterministic":
        return deterministic(args.only)
    if args.command == "setup":
        if not args.case:
            sys.exit("setup requires --case")
        setup(args.case)
        return 0
    if args.command == "collect":
        if not (args.case and args.results):
            sys.exit("collect requires --case --results")
        collect(args.case, args.results)
        return 0
    if not args.results:
        sys.exit("compare requires --results")
    return compare(args.results, args.only)


if __name__ == "__main__":
    sys.exit(main())
