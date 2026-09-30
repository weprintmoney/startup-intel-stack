#!/usr/bin/env python3
"""Unit tests for scripts/check-docs-sync.py. Run by schema-validate.yml."""

import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cds", HERE / "check-docs-sync.py")
cds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cds)


class TransitionsParsing(unittest.TestCase):
    def test_simple_row(self):
        md = "## Claim states\n\n| From | To |\n|---|---|\n| `spec-pending` | `spec-approved`, `abandoned` |\n"
        self.assertEqual(cds.extract_docs_transitions(md), {"spec-pending": {"spec-approved", "abandoned"}})

    def test_row_with_explanatory_prose_in_the_to_cell(self):
        md = ("## Claim states\n\n| From | To |\n|---|---|\n"
              "| `implementing` | `implementing` (added 2026-09-17, resumes a run), `pr-open`, `abandoned` |\n")
        self.assertEqual(cds.extract_docs_transitions(md), {"implementing": {"implementing", "pr-open", "abandoned"}})

    def test_row_with_two_from_states_and_no_to_states(self):
        # The real reference.md shape for terminal states: one row, two
        # from-states packed into the first cell, "terminal" prose (no
        # backticks) in the second -- must map both to an empty set, the
        # same as transitions.json's `"merged": []`.
        md = "## Claim states\n\n| From | To |\n|---|---|\n| `merged`, `abandoned` | terminal |\n"
        self.assertEqual(cds.extract_docs_transitions(md), {"merged": set(), "abandoned": set()})

    def test_stops_at_the_next_h2(self):
        md = ("## Claim states\n\n| `a` | `b` |\n\n"
              "## Workflows\n\n| `c` | `d` |\n")
        self.assertEqual(cds.extract_docs_transitions(md), {"a": {"b"}})

    def test_no_header_returns_empty(self):
        self.assertEqual(cds.extract_docs_transitions("nothing here"), {})


class DiffTransitions(unittest.TestCase):
    def test_matching_reports_nothing(self):
        live = {"a": {"b", "c"}}
        docs = {"a": {"b", "c"}}
        self.assertEqual(cds.diff_transitions(live, docs), [])

    def test_missing_edge_in_docs(self):
        live = {"a": {"b", "c"}}
        docs = {"a": {"b"}}
        findings = cds.diff_transitions(live, docs)
        self.assertEqual(len(findings), 1)
        self.assertIn("'c'", findings[0])

    def test_missing_state_row_in_docs(self):
        live = {"a": {"b"}, "z": set()}
        docs = {"a": {"b"}}
        findings = cds.diff_transitions(live, docs)
        self.assertEqual(len(findings), 1)
        self.assertIn("`z`", findings[0])
        self.assertIn("no row", findings[0])

    def test_stale_edge_in_docs_no_longer_in_transitions_json(self):
        live = {"a": {"b"}}
        docs = {"a": {"b", "c"}}
        findings = cds.diff_transitions(live, docs)
        self.assertEqual(len(findings), 1)
        self.assertIn("no longer allows", findings[0])

    def test_state_documented_that_does_not_exist_at_all(self):
        live = {"a": {"b"}}
        docs = {"a": {"b"}, "ghost": set()}
        findings = cds.diff_transitions(live, docs)
        self.assertEqual(len(findings), 1)
        self.assertIn("not a key in transitions.json", findings[0])


class DiffWorkflowFiles(unittest.TestCase):
    def test_excluded_workflows_never_flagged_either_direction(self):
        # lint.yml is on disk but deliberately undocumented; schema-validate.yml
        # is (hypothetically) documented but excluded -- neither should fire.
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            wf_dir = Path(d)
            (wf_dir / "lint.yml").write_text("name: Lint\n")
            (wf_dir / "implement.yml").write_text("name: Implement\n")
            md = "See `implement.yml` and `schema-validate.yml`."
            findings = cds.diff_workflow_files(wf_dir, md)
        self.assertEqual(findings, [])

    def test_new_undocumented_workflow_is_flagged(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            wf_dir = Path(d)
            (wf_dir / "brand-new-reaper.yml").write_text("name: New\n")
            findings = cds.diff_workflow_files(wf_dir, "no mention of it here")
        self.assertEqual(len(findings), 1)
        self.assertIn("brand-new-reaper.yml", findings[0])
        self.assertIn("never mentions it", findings[0])

    def test_removed_workflow_still_documented_is_flagged(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            wf_dir = Path(d)  # empty -- the file was deleted
            findings = cds.diff_workflow_files(wf_dir, "still references `renamed-away.yml` here")
        self.assertEqual(len(findings), 1)
        self.assertIn("renamed-away.yml", findings[0])
        self.assertIn("no longer exists", findings[0])


if __name__ == "__main__":
    unittest.main()
