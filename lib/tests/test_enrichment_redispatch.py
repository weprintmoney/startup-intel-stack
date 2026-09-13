"""Unit tests for lib/enrichment_redispatch.py.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import enrichment_redispatch as er  # noqa: E402


def write(path: Path, records: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records))


class Decide(unittest.TestCase):
    def test_zero_remaining_hands_off_regardless_of_commit(self):
        self.assertTrue(er.decide(0, committed=True))
        self.assertTrue(er.decide(0, committed=False))

    def test_remaining_and_committed_continues(self):
        self.assertFalse(er.decide(5, committed=True))

    def test_remaining_and_not_committed_hands_off(self):
        self.assertTrue(er.decide(5, committed=False))


class CountRemainingNormal(unittest.TestCase):
    def test_counts_unenriched_leads_by_identity_key(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            enriched = root / "leads/enriched"
            prefiltered = root / "leads/pre-filtered"
            write(enriched / "2026-09-01.json", [
                {"contact_name": "Ada Lovelace", "company_name": "Acme"},
            ])
            write(prefiltered / "2026-09-01.json", [
                {"contact_name": "Ada Lovelace", "company_name": "Acme"},  # already enriched
                {"contact_name": "Grace Hopper", "company_name": "Beta"},  # not yet
            ])
            self.assertEqual(er.count_remaining_normal(enriched, prefiltered), 1)

    def test_identity_match_is_case_and_whitespace_insensitive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            enriched = root / "leads/enriched"
            prefiltered = root / "leads/pre-filtered"
            write(enriched / "e.json", [{"contact_name": " Ada Lovelace ", "company_name": "ACME"}])
            write(prefiltered / "p.json", [{"contact_name": "ada lovelace", "company_name": "acme"}])
            self.assertEqual(er.count_remaining_normal(enriched, prefiltered), 0)

    def test_rejects_files_are_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            enriched = root / "leads/enriched"
            prefiltered = root / "leads/pre-filtered"
            write(prefiltered / "2026-09-01-rejects.json", [
                {"contact_name": "Rejected Lead", "company_name": "Nope"},
            ])
            self.assertEqual(er.count_remaining_normal(enriched, prefiltered), 0)

    def test_unreadable_file_treated_as_empty_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            enriched = root / "leads/enriched"
            prefiltered = root / "leads/pre-filtered"
            prefiltered.mkdir(parents=True)
            (prefiltered / "broken.json").write_text("{not json")
            # Must not raise.
            self.assertEqual(er.count_remaining_normal(enriched, prefiltered), 0)


class CountRemainingSignalRefresh(unittest.TestCase):
    def test_deliverable_lead_missing_signals_counts(self):
        with tempfile.TemporaryDirectory() as d:
            enriched = Path(d) / "leads/enriched"
            write(enriched / "e.json", [
                {"email": "a@example.com", "email_status": "deliverable"},
            ])
            self.assertEqual(er.count_remaining_signal_refresh(enriched), 1)

    def test_lead_with_a_signal_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            enriched = Path(d) / "leads/enriched"
            write(enriched / "e.json", [
                {"email": "a@example.com", "email_status": "deliverable", "pain_points": ["x"]},
            ])
            self.assertEqual(er.count_remaining_signal_refresh(enriched), 0)

    def test_already_checked_lead_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            enriched = Path(d) / "leads/enriched"
            write(enriched / "e.json", [
                {"email": "a@example.com", "email_status": "deliverable", "signals_checked": True},
            ])
            self.assertEqual(er.count_remaining_signal_refresh(enriched), 0)

    def test_non_deliverable_lead_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            enriched = Path(d) / "leads/enriched"
            write(enriched / "e.json", [
                {"email": "a@example.com", "email_status": "bounced"},
            ])
            self.assertEqual(er.count_remaining_signal_refresh(enriched), 0)

    def test_duplicate_email_counted_once(self):
        with tempfile.TemporaryDirectory() as d:
            enriched = Path(d) / "leads/enriched"
            write(enriched / "e1.json", [{"email": "a@example.com", "email_status": "deliverable"}])
            write(enriched / "e2.json", [{"email": "A@Example.com", "email_status": "deliverable"}])
            self.assertEqual(er.count_remaining_signal_refresh(enriched), 1)

    def test_suppressed_email_excluded(self):
        import os

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            enriched = root / "leads/enriched"
            write(enriched / "e.json", [{"email": "a@blocked.com", "email_status": "deliverable"}])
            sup_path = root / "suppression" / "list.jsonl"
            sup_path.parent.mkdir(parents=True)
            sup_path.write_text(json.dumps({"email": "a@blocked.com"}) + "\n")
            old_env = os.environ.get("SUPPRESSION_LIST_PATH")
            os.environ["SUPPRESSION_LIST_PATH"] = str(sup_path)
            try:
                self.assertEqual(er.count_remaining_signal_refresh(enriched), 0)
            finally:
                if old_env is None:
                    os.environ.pop("SUPPRESSION_LIST_PATH", None)
                else:
                    os.environ["SUPPRESSION_LIST_PATH"] = old_env

    def test_suppressed_domain_excluded(self):
        import os

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            enriched = root / "leads/enriched"
            write(enriched / "e.json", [{"email": "a@blocked.com", "email_status": "deliverable"}])
            sup_path = root / "suppression" / "list.jsonl"
            sup_path.parent.mkdir(parents=True)
            sup_path.write_text(json.dumps({"domain": "blocked.com"}) + "\n")
            old_env = os.environ.get("SUPPRESSION_LIST_PATH")
            os.environ["SUPPRESSION_LIST_PATH"] = str(sup_path)
            try:
                self.assertEqual(er.count_remaining_signal_refresh(enriched), 0)
            finally:
                if old_env is None:
                    os.environ.pop("SUPPRESSION_LIST_PATH", None)
                else:
                    os.environ["SUPPRESSION_LIST_PATH"] = old_env


if __name__ == "__main__":
    unittest.main()
