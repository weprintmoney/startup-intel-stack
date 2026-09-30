#!/usr/bin/env python3
"""Unit tests for scripts/verify-claims.py — the deterministic half of the
claim-verify gate. Stdlib-only (unittest). Run: `python3 scripts/verify-claims_test.py`.
"""

from __future__ import annotations

import importlib.util as _iu
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SPEC = _iu.spec_from_file_location("verify_claims", HERE / "verify-claims.py")
vc = _iu.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(vc)

FIXTURES = HERE.parent / "evals" / "claim-verify-cases" / "_fixtures"

RETIRED_MD = """# Claims vetted

## Retired claims — never publish

Intro paragraph.

| Retired phrase | Why | Say instead |
|---|---|---|
| "proxy mode" / "proxy layer" / "sits in front of" | framing | "standalone" |
| "point it at Postgres" / "Postgres, Redis" (as backing stores) | proxy | "tiered" |
| "no new database to staff/operate/manage" / "isn't another database" | claim | Omit |
| "MySQL" (as a supported backend) | never supported | — |

## Next section

| not | a retired | table |
"""


class RetiredPhraseParsing(unittest.TestCase):
    def test_table_first_column_parsed(self):
        phrases = vc.parse_retired_phrases_md(RETIRED_MD)
        self.assertIn("proxy mode", phrases)
        self.assertIn("sits in front of", phrases)
        self.assertIn("point it at Postgres", phrases)
        self.assertIn("Postgres, Redis", phrases)
        self.assertIn("MySQL", phrases)
        self.assertIn("isn't another database", phrases)

    def test_qualifiers_dropped_and_slash_alternatives_expanded(self):
        phrases = vc.parse_retired_phrases_md(RETIRED_MD)
        self.assertNotIn("(as backing stores)", " ".join(phrases))
        self.assertIn("no new database to staff", phrases)
        self.assertIn("no new database to operate", phrases)
        self.assertIn("no new database to manage", phrases)

    def test_stops_at_next_heading(self):
        phrases = vc.parse_retired_phrases_md(RETIRED_MD)
        self.assertNotIn("not", phrases)
        self.assertNotIn("a retired", phrases)

    def test_no_section_returns_empty(self):
        self.assertEqual(vc.parse_retired_phrases_md("# nothing here\n| a | b |\n"), [])

    def test_features_json_precedence_shape(self):
        feats = {"features": [
            {"id": "proxy", "status": "retired", "retired_claim_phrases": ["proxy mode", " sits in front of "]},
            {"id": "s3", "status": "ga", "retired_claim_phrases": []},
        ]}
        self.assertEqual(vc.retired_phrases_from_features(feats), ["proxy mode", "sits in front of"])
        # bare list form
        self.assertEqual(vc.retired_phrases_from_features(feats["features"]), ["proxy mode", "sits in front of"])


class PhraseMatching(unittest.TestCase):
    def test_case_and_whitespace_insensitive_with_boundaries(self):
        rx = vc.phrase_regex("sits in front of")
        self.assertIsNotNone(rx.search("example-app Sits  in\nfront of your DB"))
        self.assertIsNone(rx.search("visits in front of"))   # left boundary
        rx2 = vc.phrase_regex("MySQL")
        self.assertIsNotNone(rx2.search("uses mysql as"))
        self.assertIsNone(rx2.search("mysqldump"))


class SentenceExtraction(unittest.TestCase):
    def test_versions_and_paths_stay_whole(self):
        text = "Intro line.\nThe store moved in v0.17.0 per src/x/y.py:12 today. Next sentence."
        pos = text.index("v0.17.0")
        s = vc._sentence_at(text, pos)
        self.assertIn("v0.17.0", s)
        self.assertIn("src/x/y.py:12", s)
        self.assertNotIn("Next sentence", s)
        self.assertNotIn("Intro line", s)


def _sources(tmp: Path) -> Path:
    out = tmp / "sources"
    argv = ["sources", "--internal-docs", str(FIXTURES / "internal-docs"),
            "--docs-repo", str(FIXTURES / "docs-public"), "--out", str(out)]
    sys.argv = ["verify-claims.py", *argv]
    self_main = vc.main()
    assert self_main == 0
    return out


class SourcesCommand(unittest.TestCase):
    def test_manifest_and_retired_phrases(self):
        with tempfile.TemporaryDirectory() as td:
            out = _sources(Path(td))
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertTrue(manifest["sources"]["graph.json"]["present"])
            self.assertFalse(manifest["sources"]["features.json"]["present"])
            self.assertEqual(manifest["retired_phrases_from"], "claims-vetted.md")
            phrases = (out / "retired-phrases.txt").read_text().splitlines()
            self.assertIn("separates compute from storage", phrases)
            self.assertTrue((out / "changelog.mdx").is_file())

    def test_features_json_wins_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            # Copy the fixture internal-docs and add a features.json
            import shutil
            idocs = Path(td) / "internal-docs"
            shutil.copytree(FIXTURES / "internal-docs", idocs)
            (idocs / ".claude" / "indexes" / "features.json").write_text(json.dumps({
                "features": [{"id": "proxy-mode", "status": "retired",
                              "retired_claim_phrases": ["proxy mode", "sits in front of"]}]
            }))
            out = Path(td) / "sources"
            sys.argv = ["verify-claims.py", "sources", "--internal-docs", str(idocs), "--out", str(out)]
            self.assertEqual(vc.main(), 0)
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(manifest["retired_phrases_from"], "features.json")
            self.assertEqual((out / "retired-phrases.txt").read_text().splitlines(),
                             ["proxy mode", "sits in front of"])
            self.assertFalse(manifest["sources"]["changelog.mdx"]["present"])  # no docs repo given


class ExtractSpec(unittest.TestCase):
    def _extract(self, text: str, product: bool = True, agent_ops: bool = False) -> list[dict]:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out = _sources(tmp)
            art = tmp / "artifact.md"
            art.write_text(text)
            claims = tmp / "claims.json"
            argv = ["verify-claims.py", "extract", "--kind", "spec", "--artifact", str(art),
                    "--artifact-ref", "x.md", "--sources", str(out),
                    "--internal-docs", str(FIXTURES / "internal-docs"), "--out", str(claims)]
            if product:
                argv += ["--product", str(FIXTURES / "product")]
            if agent_ops:
                argv += ["--agent-ops", str(FIXTURES / "agent-ops")]
            sys.argv = argv
            self.assertEqual(vc.main(), 0)
            return json.loads(claims.read_text())["claims"]

    def test_missing_path_contradicted_existing_path_pending(self):
        claims = self._extract(
            "Pool at `src/example_app/storage/postgres_pool.py:12`.\n"
            "Default at `src/example_app/service/config.py:7`.\n"
        )
        missing = next(c for c in claims if "postgres_pool.py:12" in c["claim"])
        self.assertEqual(missing["verdict"], "contradicted")
        existing = next(c for c in claims if "config.py:7" in c["claim"])
        self.assertEqual(existing["verdict"], "pending")
        self.assertIn("21 lines", existing["evidence"])

    def test_line_beyond_eof_contradicted(self):
        claims = self._extract("See `src/example_app/service/config.py:999`.")
        c = next(c for c in claims if "config.py:999" in c["claim"])
        self.assertEqual(c["verdict"], "contradicted")
        self.assertIn("21 lines", c["evidence"])

    def test_guards_path_contradicted_without_agent_ops_root(self):
        # Reproduces the bug: a citation into guards/*.paths (which lives in
        # the agent-ops repo, not product or internal-docs) is unconditionally
        # "not found" when no agent-ops root is given.
        claims = self._extract("Guarded at `guards/example-app-sdk-js.paths:2`.", agent_ops=False)
        c = next(c for c in claims if "example-app-sdk-js.paths:2" in c["claim"])
        self.assertEqual(c["verdict"], "contradicted")

    def test_guards_path_verified_with_agent_ops_root(self):
        claims = self._extract("Guarded at `guards/example-app-sdk-js.paths:2`.", agent_ops=True)
        c = next(c for c in claims if "example-app-sdk-js.paths:2" in c["claim"])
        self.assertEqual(c["verdict"], "pending")
        self.assertIn("agent-ops/guards/example-app-sdk-js.paths", c["source"])

    def test_urls_are_not_path_citations(self):
        claims = self._extract("See https://docs.example.com/versions/v0.17.x/intro/foo.mdx:12 for details.")
        self.assertFalse(any(c["kind"] == "path-citation" for c in claims))

    def test_no_product_checkout_marks_unverified(self):
        claims = self._extract("Default at `src/example_app/service/config.py:7`.", product=False)
        # internal-docs is still given, so the path is searched there and not found -> contradicted
        c = next(c for c in claims if "config.py:7" in c["claim"])
        self.assertEqual(c["verdict"], "contradicted")

    def test_graph_ids_and_versions(self):
        claims = self._extract(
            "Leans on `adr-0023` and `component/backing-stores`; `adr-0041` decided X.\n"
            "Shipped in v0.17.0; target v0.19.\n"
        )
        g = {c["claim"]: c["verdict"] for c in claims if c["kind"] == "graph-node"}
        self.assertEqual(g["references graph node `adr-0023`"], "verified")
        self.assertEqual(g["references graph node `component/backing-stores`"], "verified")
        self.assertEqual(g["references graph node `adr-0041` — not in graph.json"], "unverified")
        import re as _re
        v = {_re.search(r"`(v[\d.x]+)`", c["claim"]).group(1): c["verdict"]
             for c in claims if c["kind"] == "version"}
        self.assertEqual(v["v0.17.0"], "verified")
        self.assertEqual(v["v0.19"], "pending")

    def test_retired_phrase_in_spec_is_pending_not_contradicted(self):
        claims = self._extract("Operators used to point it at Postgres before v0.17.0.")
        c = next(c for c in claims if c["kind"] == "retired-phrase")
        self.assertEqual(c["verdict"], "pending")
        self.assertIn("point it at Postgres", c["claim"])


class ExtractReleaseFindings(unittest.TestCase):
    def _extract(self, doc: dict) -> dict:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out = _sources(tmp)
            art = tmp / "artifact.json"
            art.write_text(json.dumps(doc))
            claims = tmp / "claims.json"
            sys.argv = ["verify-claims.py", "extract", "--kind", "release-findings", "--artifact", str(art),
                        "--artifact-ref", "v0.17.0", "--sources", str(out),
                        "--internal-docs", str(FIXTURES / "internal-docs"), "--out", str(claims)]
            self.assertEqual(vc.main(), 0)
            return json.loads(claims.read_text())

    def _finding(self, pr: int, summary: str, verdict: str = "market-worthy", evidence=None) -> dict:
        return {"pr_number": pr, "pr_title": "t", "pr_url": f"https://github.com/example-org/example-app-core/pull/{pr}",
                "summary": summary, "scores": {}, "total": 7, "verdict": verdict,
                "evidence": evidence if evidence is not None else
                [{"source": "01-market-intelligence/ideal-customer-profile.mdx", "note": "n"}]}

    def test_retired_phrase_in_finding_is_contradicted_and_scoped(self):
        doc = {"findings": [
            self._finding(1, "example-app sits in front of your bucket."),
            self._finding(2, "Also sits in front of things.", verdict="not-market-worthy"),
        ]}
        res = self._extract(doc)
        self.assertEqual(res["scope_finding_prs"], [1])
        rp = [c for c in res["claims"] if c["kind"] == "retired-phrase"]
        self.assertEqual(len(rp), 1)
        self.assertEqual(rp[0]["verdict"], "contradicted")
        self.assertEqual(rp[0]["finding_pr"], 1)

    def test_evidence_sources(self):
        doc = {"findings": [self._finding(5, "ok", evidence=[
            {"source": "01-market-intelligence/ideal-customer-profile.mdx"},
            {"source": "99-nope/missing.md"},
            {"source": "https://github.com/example-org/example-app-core/pull/5"},
            {"source": "https://example.com/competitor-page"},
        ])]}
        claims = {c["location"]: c["verdict"] for c in self._extract(doc)["claims"] if c["kind"] == "evidence-source"}
        self.assertEqual(claims["evidence[0]"], "pending")
        self.assertEqual(claims["evidence[1]"], "contradicted")
        self.assertEqual(claims["evidence[2]"], "pending")
        self.assertEqual(claims["evidence[3]"], "contradicted")


class Aggregate(unittest.TestCase):
    def _doc(self, *claims: dict) -> dict:
        return {"artifact_kind": "spec", "artifact_ref": "x.md",
                "sources_manifest": {"sources": {"graph.json": {"present": True, "sha256": "abc"},
                                                 "features.json": {"present": False, "sha256": None}},
                                     "internal_docs_ref": "deadbee"},
                "claims": list(claims)}

    def _c(self, cid, verdict, kind="path-citation", **kw):
        base = {"id": cid, "kind": kind, "claim": f"claim {cid}", "location": "L1", "verdict": verdict,
                "checked_by": "deterministic", "source": None, "evidence": None, "note": None, "finding_pr": None}
        base.update(kw)
        return base

    def test_missing_model_verdict_yields_unverified_never_verified(self):
        final = vc.aggregate(self._doc(self._c("d-01", "verified")), None, "http://r")
        self.assertEqual(final["verdict"], "unverified")
        self.assertTrue(any(c["id"] == "m-00" for c in final["claims"]))

    def test_pending_unresolved_becomes_unverified(self):
        final = vc.aggregate(self._doc(self._c("d-01", "pending")), {"claims": [
            {"id": "m-01", "kind": "product-behavior", "claim": "fine", "verdict": "verified", "source": "s"}]}, "http://r")
        d01 = next(c for c in final["claims"] if c["id"] == "d-01")
        self.assertEqual(d01["verdict"], "unverified")
        self.assertEqual(final["verdict"], "unverified")

    def test_deterministic_contradiction_not_overridable_and_worst_wins(self):
        final = vc.aggregate(self._doc(self._c("d-01", "contradicted"), self._c("d-02", "pending")), {"claims": [
            {"id": "d-01", "verdict": "verified", "source": "s"},          # attempt to flip — ignored
            {"id": "d-02", "verdict": "verified", "source": "s", "evidence": "e"},
            {"id": "m-01", "kind": "bogus-kind", "claim": "x", "verdict": "nonsense"},
        ]}, "http://r")
        by = {c["id"]: c for c in final["claims"]}
        self.assertEqual(by["d-01"]["verdict"], "contradicted")
        self.assertEqual(by["d-02"]["verdict"], "verified")
        self.assertEqual(by["d-02"]["checked_by"], "model")
        self.assertEqual(by["m-01"]["verdict"], "unverified")   # coerced
        self.assertEqual(by["m-01"]["kind"], "other")
        self.assertEqual(final["verdict"], "contradicted")
        self.assertEqual(final["counts"], {"verified": 1, "unverified": 1, "contradicted": 1})

    def test_all_verified(self):
        final = vc.aggregate(self._doc(self._c("d-01", "verified")), {"claims": [
            {"id": "m-01", "kind": "product-behavior", "claim": "x", "verdict": "verified", "source": "s"}]}, "http://r")
        self.assertEqual(final["verdict"], "verified")
        self.assertIsNone(next(c for c in final["claims"] if c["id"] == "m-01")["material"])

    # A model-enumerated "1,560 hand-written lines"
    # claim was off by two on `wc -l`; the argument it supported was
    # unchanged. The verifier said so in its note, and the PR was still
    # drafted and produced two fixup PRs. An explicit `material: false`
    # from the model turns that into a flag, not a block.
    def test_immaterial_model_contradiction_flags_instead_of_blocking(self):
        final = vc.aggregate(self._doc(self._c("d-01", "verified")), {"claims": [
            {"id": "m-01", "kind": "doc-statement", "claim": "1,560 hand-written lines", "location": "L173",
             "verdict": "contradicted", "material": False, "source": "wc -l", "evidence": "1,558"}]}, "http://r")
        m01 = next(c for c in final["claims"] if c["id"] == "m-01")
        self.assertEqual(m01["verdict"], "contradicted")
        self.assertIs(m01["material"], False)
        self.assertEqual(final["verdict"], "unverified")
        self.assertEqual(final["counts"]["contradicted"], 1)
        md = vc.render_md(final)
        self.assertIn("UNVERIFIED", md)
        self.assertIn("1 contradicted, 1 immaterial", md)
        self.assertIn("immaterial, fix in a follow-up", md)
        self.assertNotIn("blocks approval", md)

    def test_material_defaults_to_true_and_blocks(self):
        for material in ({}, {"material": None}, {"material": "false"}, {"material": 0}):
            final = vc.aggregate(self._doc(self._c("d-01", "verified")), {"claims": [
                {"id": "m-01", "kind": "product-behavior", "claim": "x", "verdict": "contradicted",
                 "source": "changelog", "evidence": "removed", **material}]}, "http://r")
            m01 = next(c for c in final["claims"] if c["id"] == "m-01")
            self.assertIs(m01["material"], True, material)
            self.assertEqual(final["verdict"], "contradicted", material)
            self.assertIn("blocks approval", vc.render_md(final))

    def test_deterministic_contradiction_is_never_immaterial(self):
        final = vc.aggregate(self._doc(self._c("d-01", "contradicted", evidence="not present")), {"claims": [
            {"id": "d-01", "verdict": "contradicted", "material": False, "source": "s"}]}, "http://r")
        d01 = next(c for c in final["claims"] if c["id"] == "d-01")
        self.assertEqual(d01["checked_by"], "deterministic")
        self.assertIs(d01["material"], True)
        self.assertEqual(final["verdict"], "contradicted")

    def test_pending_resolved_as_immaterial_by_model(self):
        # A drifted path:line — the statement sits a few lines from the cited
        # line — is a model resolution of a pre-pass `pending` claim.
        final = vc.aggregate(self._doc(self._c("d-01", "pending")), {"claims": [
            {"id": "d-01", "verdict": "contradicted", "material": False, "source": "product/x.py:670",
             "evidence": "statement is at line 670, cited 669"}]}, "http://r")
        d01 = next(c for c in final["claims"] if c["id"] == "d-01")
        self.assertEqual(d01["checked_by"], "model")
        self.assertIs(d01["material"], False)
        self.assertEqual(final["verdict"], "unverified")

    def test_material_blocks_beat_immaterial_ones(self):
        final = vc.aggregate(self._doc(self._c("d-01", "verified")), {"claims": [
            {"id": "m-01", "kind": "doc-statement", "claim": "count", "verdict": "contradicted",
             "material": False, "source": "s"},
            {"id": "m-02", "kind": "feature-status", "claim": "postgres", "verdict": "contradicted",
             "source": "changelog"}]}, "http://r")
        self.assertEqual(final["verdict"], "contradicted")
        md = vc.render_md(final)
        self.assertIn("blocks approval", md)
        self.assertIn("immaterial, fix in a follow-up", md)

    def test_markdown_render_and_idempotent_patch(self):
        final = vc.aggregate(self._doc(self._c("d-01", "contradicted", evidence="not present")), None, "http://r")
        md = vc.render_md(final)
        self.assertIn("CONTRADICTED", md)
        self.assertIn("features.json", md)
        self.assertIn(vc.MD_START, md)
        body = "Original PR body.\n"
        once = vc.replace_md_block(body, md)
        twice = vc.replace_md_block(once, md)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(vc.MD_START), 1)
        self.assertTrue(once.startswith("Original PR body."))

    def test_schema_conformance_when_jsonschema_available(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema not installed")
        schema = json.loads((HERE.parent / "schemas" / "claim-verdict.schema.json").read_text())
        final = vc.aggregate(self._doc(self._c("d-01", "pending")), {"claims": [
            {"id": "d-01", "verdict": "verified", "source": "s", "evidence": "e"},
            {"id": "m-01", "kind": "feature-status", "claim": "x", "location": "L3", "verdict": "contradicted",
             "source": "changelog", "evidence": "removed", "finding_pr": None},
            {"id": "m-02", "kind": "doc-statement", "claim": "1,560 lines", "location": "L173",
             "verdict": "contradicted", "material": False, "source": "wc -l", "evidence": "1,558",
             "finding_pr": None}]}, "https://r")
        errs = list(Draft202012Validator(schema).iter_errors(final))
        self.assertEqual(errs, [], [e.message for e in errs])


if __name__ == "__main__":
    unittest.main(verbosity=1)
