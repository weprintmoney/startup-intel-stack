#!/usr/bin/env python3
"""CI gate: every citation root `scan_path_citations` knows
about (verify-claims.py's `CITATION_ROOTS`) must have at least one golden-set
case in evals/claim-verify-cases/ that resolves a real path-citation against
it — no model, no API key.

Closes a gap that shipped once: a change added the `agent-ops` root to the
deterministic path-citation checker, but the 5-case golden set never grew a
case that exercised it, so the fixture that would have caught a citation
against `guards/*.paths` being wrongly scored `contradicted` didn't exist —
three spec-draft attempts burned before the live miss was
noticed. This check makes that class of gap fail CI instead of waiting for
another live miss: add a new root to `CITATION_ROOTS` (or drop one) and
forget the matching case, and this fails with the missing root's name.

Reuses run-claim-verify-evals.py's `materialize()` to run the deterministic
pre-pass for every case (no model) and inspects the resulting claims.json for
a `path-citation` claim that actually resolved (`verdict == "pending"`,
meaning the cited file exists and the line is in range) with a `source`
naming that root.

Run directly: `python3 scripts/check-citation-root-coverage.py`.
"""
from __future__ import annotations

import importlib.util as _iu
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, filename: str):
    spec = _iu.spec_from_file_location(name, HERE / filename)
    mod = _iu.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


vc = _load("verify_claims", "verify-claims.py")
rc = _load("run_claim_verify_evals", "run-claim-verify-evals.py")


def exercised_roots() -> dict[str, list[str]]:
    """-> {root name: [case slugs that resolve a path-citation against it]}."""
    hits: dict[str, list[str]] = {name: [] for name, _ in vc.CITATION_ROOTS}
    work = Path(tempfile.mkdtemp(prefix="citation-root-coverage-"))
    try:
        for slug in rc.list_cases(None):
            rc.materialize(slug, work)
            claims = json.loads((work / "claims.json").read_text())["claims"]
            for c in claims:
                if c.get("kind") != "path-citation" or c.get("verdict") != "pending":
                    continue
                source = c.get("source") or ""
                for name, _ in vc.CITATION_ROOTS:
                    if (source == name or source.startswith(f"{name}/")) and slug not in hits[name]:
                        hits[name].append(slug)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return hits


def main() -> int:
    known = [name for name, _ in vc.CITATION_ROOTS]
    hits = exercised_roots()
    missing = [name for name in known if not hits.get(name)]
    if missing:
        print("citation-root golden-set coverage FAILED:")
        for name in missing:
            print(f"  - {name!r}: verify-claims.py's CITATION_ROOTS knows this root, but no "
                  f"evals/claim-verify-cases/*/ case resolves a path-citation against it "
                  f"(verdict == pending, source starting with {name!r}/). Add one.")
        return 1
    print("citation-root golden-set coverage OK: " +
          ", ".join(f"{name} ({', '.join(hits[name])})" for name in known))
    return 0


if __name__ == "__main__":
    sys.exit(main())
