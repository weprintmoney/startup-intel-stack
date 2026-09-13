"""Mode-gate behaviour for lib/config.py.

The mode decides how much of the system is switched on. Its failure mode is
silent: a value nothing recognizes used to resolve to the most restrictive
tier with no message, which looks exactly like "the pipeline is broken."
These tests pin the mapping, the legacy aliases, and the loud fallback.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402


def profile(**company):
    return {"company": company}


class NormalizeMode(unittest.TestCase):
    def test_canonical_names_pass_through(self):
        for m in ("docs-only", "find-leads", "find-and-draft"):
            self.assertEqual(config.normalize_mode(m), m)

    def test_legacy_stage_names_map_across(self):
        self.assertEqual(config.normalize_mode("pre-seed"), "docs-only")
        self.assertEqual(config.normalize_mode("seed"), "find-leads")
        self.assertEqual(config.normalize_mode("series-a"), "find-and-draft")

    def test_case_and_whitespace_tolerated(self):
        self.assertEqual(config.normalize_mode("  Find-Leads "), "find-leads")
        self.assertEqual(config.normalize_mode("Series-A"), "find-and-draft")

    def test_unrecognized_returns_none(self):
        for bad in ("growth", "seed-stage", "", None, "series a"):
            self.assertIsNone(config.normalize_mode(bad))


class Mode(unittest.TestCase):
    def test_reads_company_mode(self):
        self.assertEqual(config.mode(profile(mode="find-leads")), "find-leads")

    def test_falls_back_to_legacy_company_stage(self):
        self.assertEqual(config.mode(profile(stage="series-a")), "find-and-draft")

    def test_mode_wins_over_stage_when_both_present(self):
        p = profile(mode="docs-only", stage="series-a")
        self.assertEqual(config.mode(p), "docs-only")

    def test_missing_value_defaults_to_most_restrictive_silently(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(config.mode(profile()), "docs-only")
        self.assertEqual(buf.getvalue(), "")  # absence isn't a typo — no warning

    def test_unrecognized_value_warns_loudly(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(config.mode(profile(mode="groth")), "docs-only")
        out = buf.getvalue()
        self.assertIn("::warning::", out)
        self.assertIn("groth", out)


class ModeAtLeast(unittest.TestCase):
    def test_ordering(self):
        docs = profile(mode="docs-only")
        leads = profile(mode="find-leads")
        draft = profile(mode="find-and-draft")

        self.assertTrue(config.mode_at_least("docs-only", docs))
        self.assertFalse(config.mode_at_least("find-leads", docs))
        self.assertFalse(config.mode_at_least("find-and-draft", docs))

        self.assertTrue(config.mode_at_least("find-leads", leads))
        self.assertFalse(config.mode_at_least("find-and-draft", leads))

        self.assertTrue(config.mode_at_least("find-and-draft", draft))
        self.assertTrue(config.mode_at_least("docs-only", draft))

    def test_required_accepts_legacy_names_too(self):
        leads = profile(mode="find-leads")
        self.assertTrue(config.mode_at_least("seed", leads))
        self.assertFalse(config.mode_at_least("series-a", leads))

    def test_unknown_required_raises_rather_than_passing_silently(self):
        with self.assertRaises(ValueError):
            config.mode_at_least("whenever", profile(mode="find-and-draft"))

    def test_stage_at_least_still_works(self):
        self.assertTrue(config.stage_at_least("seed", profile(stage="series-a")))
        self.assertFalse(config.stage_at_least("series-a", profile(stage="seed")))


if __name__ == "__main__":
    unittest.main()
