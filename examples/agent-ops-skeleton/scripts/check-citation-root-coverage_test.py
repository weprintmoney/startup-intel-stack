#!/usr/bin/env python3
"""Unit tests for scripts/check-citation-root-coverage.py.

Mocks `run_claim_verify_evals.list_cases`/`.materialize` so these tests never
touch the real golden set or shell out to verify-claims.py — they exercise
only the coverage-counting and pass/fail logic against synthetic claims.json
content. The real golden set is covered by run-claim-verify-evals.py's own
`deterministic` command and asserted end-to-end by running this script
directly (see the PR description).
"""
from __future__ import annotations

import importlib.util as _iu
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent


def _load(name: str, filename: str):
    spec = _iu.spec_from_file_location(name, HERE / filename)
    mod = _iu.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


ccrc = _load("check_citation_root_coverage", "check-citation-root-coverage.py")


def _fake_materialize(claims_by_case: dict[str, list[dict]]):
    def _materialize(slug: str, work: Path) -> dict:
        work.mkdir(parents=True, exist_ok=True)
        (work / "claims.json").write_text(json.dumps({"claims": claims_by_case[slug]}))
        return {}
    return _materialize


class ExercisedRoots(unittest.TestCase):
    ROOTS = (("product", "product"), ("internal-docs", "internal"), ("agent-ops", "agent_ops"))

    def _run(self, claims_by_case: dict[str, list[dict]]) -> dict[str, list[str]]:
        with mock.patch.object(ccrc.vc, "CITATION_ROOTS", self.ROOTS), \
             mock.patch.object(ccrc.rc, "list_cases", return_value=list(claims_by_case)), \
             mock.patch.object(ccrc.rc, "materialize", side_effect=_fake_materialize(claims_by_case)):
            return ccrc.exercised_roots()

    def test_pending_citation_counts_for_its_root(self):
        hits = self._run({
            "case-a": [{"kind": "path-citation", "verdict": "pending", "source": "internal-docs/07/x.md"}],
        })
        self.assertEqual(hits["internal-docs"], ["case-a"])
        self.assertEqual(hits["product"], [])
        self.assertEqual(hits["agent-ops"], [])

    def test_contradicted_and_unverified_do_not_count_even_with_matching_source(self):
        hits = self._run({
            "case-a": [
                {"kind": "path-citation", "verdict": "contradicted", "source": "product/src/x.py"},
                {"kind": "path-citation", "verdict": "unverified", "source": "agent-ops/guards/y.paths"},
            ],
        })
        self.assertEqual(hits["product"], [])
        self.assertEqual(hits["agent-ops"], [])

    def test_non_path_citation_claims_are_ignored(self):
        hits = self._run({
            "case-a": [{"kind": "graph-node", "verdict": "verified", "source": "graph.json"}],
        })
        self.assertEqual(hits["product"], [])

    def test_source_must_be_root_name_or_root_slash_prefixed(self):
        # "product-extra" must not be mistaken for the "product" root.
        hits = self._run({
            "case-a": [{"kind": "path-citation", "verdict": "pending", "source": "product-extra/x.py"}],
        })
        self.assertEqual(hits["product"], [])

    def test_same_case_not_double_counted_for_same_root(self):
        hits = self._run({
            "case-a": [
                {"kind": "path-citation", "verdict": "pending", "source": "product/src/a.py"},
                {"kind": "path-citation", "verdict": "pending", "source": "product/src/b.py"},
            ],
        })
        self.assertEqual(hits["product"], ["case-a"])


class Main(unittest.TestCase):
    ROOTS = (("product", "product"), ("internal-docs", "internal"), ("agent-ops", "agent_ops"))

    def _run_main(self, claims_by_case: dict[str, list[dict]]) -> tuple[int, str]:
        with mock.patch.object(ccrc.vc, "CITATION_ROOTS", self.ROOTS), \
             mock.patch.object(ccrc.rc, "list_cases", return_value=list(claims_by_case)), \
             mock.patch.object(ccrc.rc, "materialize", side_effect=_fake_materialize(claims_by_case)):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = ccrc.main()
            return rc, buf.getvalue()

    def test_fails_when_a_known_root_has_no_covering_case(self):
        code, out = self._run_main({
            "case-a": [{"kind": "path-citation", "verdict": "pending", "source": "product/src/a.py"}],
        })
        self.assertEqual(code, 1)
        self.assertIn("FAILED", out)
        self.assertIn("'internal-docs'", out)
        self.assertIn("'agent-ops'", out)
        self.assertNotIn("'product'", out.split("FAILED")[1] if "FAILED" in out else out)

    def test_passes_when_every_root_is_covered(self):
        code, out = self._run_main({
            "case-a": [{"kind": "path-citation", "verdict": "pending", "source": "product/src/a.py"}],
            "case-b": [{"kind": "path-citation", "verdict": "pending", "source": "internal-docs/07/x.md"}],
            "case-c": [{"kind": "path-citation", "verdict": "pending", "source": "agent-ops/guards/y.paths"}],
        })
        self.assertEqual(code, 0)
        self.assertIn("OK", out)
        for name in ("product", "internal-docs", "agent-ops"):
            self.assertIn(name, out)

    def test_new_root_with_no_case_fails_even_if_others_pass(self):
        """Simulates adding a 4th root to verify-claims.py without a golden case (#138's contract)."""
        roots = self.ROOTS + (("docs-repo", "docs_repo"),)
        with mock.patch.object(ccrc.vc, "CITATION_ROOTS", roots), \
             mock.patch.object(ccrc.rc, "list_cases", return_value=["case-a", "case-b", "case-c"]), \
             mock.patch.object(ccrc.rc, "materialize", side_effect=_fake_materialize({
                 "case-a": [{"kind": "path-citation", "verdict": "pending", "source": "product/src/a.py"}],
                 "case-b": [{"kind": "path-citation", "verdict": "pending", "source": "internal-docs/07/x.md"}],
                 "case-c": [{"kind": "path-citation", "verdict": "pending", "source": "agent-ops/guards/y.paths"}],
             })):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = ccrc.main()
        self.assertEqual(code, 1)
        self.assertIn("'docs-repo'", buf.getvalue())


if __name__ == "__main__":
    sys.exit(unittest.main())
