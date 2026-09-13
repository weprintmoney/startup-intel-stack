"""Unit tests for lib/dedup.py.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import contextlib
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# crm.py imports requests as a type annotation evaluated at import time;
# lib-tests.yml doesn't install dependencies (same convention as
# test_send_queue.py / test_reply_monitor.py).
if "requests" not in sys.modules:
    sys.modules["requests"] = types.ModuleType("requests")
_requests_mod = sys.modules["requests"]
if not hasattr(_requests_mod, "Response"):
    _requests_mod.Response = type("Response", (), {})


import dedup  # noqa: E402


@contextlib.contextmanager
def _tmp_dir():
    p = Path(tempfile.mkdtemp())
    try:
        yield p
    finally:
        shutil.rmtree(p, ignore_errors=True)


class TestDedupLeads(unittest.TestCase):
    @patch("dedup.crm.search_by_name", return_value=[])
    def test_no_match_is_survivor(self, mock_search):
        survivors, skipped = dedup.dedup_leads([{"contact_name": "Jane Doe", "company_name": "Acme"}])
        self.assertEqual(len(survivors), 1)
        self.assertEqual(skipped, 0)
        self.assertFalse(survivors[0]["prior_contact"])

    @patch("dedup.crm.search_by_name", return_value=[{"id": "rec1"}])
    def test_match_is_skipped(self, mock_search):
        survivors, skipped = dedup.dedup_leads([{"contact_name": "Jane Doe", "company_name": "Acme"}])
        self.assertEqual(survivors, [])
        self.assertEqual(skipped, 1)

    @patch("dedup.crm.search_by_name")
    def test_no_name_is_survivor_without_crm_call(self, mock_search):
        survivors, skipped = dedup.dedup_leads([{"company_name": "Acme"}])
        self.assertEqual(len(survivors), 1)
        self.assertEqual(skipped, 0)
        self.assertFalse(survivors[0]["prior_contact"])
        mock_search.assert_not_called()

    @patch("dedup.crm.search_by_name")
    def test_mixed_batch(self, mock_search):
        mock_search.side_effect = lambda name: [{"id": "x"}] if name == "Match Me" else []
        leads = [
            {"contact_name": "Match Me", "company_name": "A"},
            {"contact_name": "New Person", "company_name": "B"},
            {"company_name": "C"},
        ]
        survivors, skipped = dedup.dedup_leads(leads)
        self.assertEqual(skipped, 1)
        self.assertEqual(len(survivors), 2)
        names = {s.get("contact_name") for s in survivors}
        self.assertEqual(names, {"New Person", None})


class TestDedupFile(unittest.TestCase):
    @patch("dedup.crm.search_by_name", return_value=[])
    def test_writes_output_and_marks_prior_contact(self, mock_search):
        with _tmp_dir() as d:
            raw = d / "raw"
            deduped = d / "deduped"
            raw.mkdir()
            deduped.mkdir()
            (raw / "2026-07-09-us-batch.json").write_text(
                json.dumps([{"contact_name": "Jane Doe", "company_name": "Acme"}])
            )
            dedup.dedup_file(raw / "2026-07-09-us-batch.json", deduped)
            out = json.loads((deduped / "2026-07-09-us-batch.json").read_text())
            self.assertEqual(len(out), 1)
            self.assertFalse(out[0]["prior_contact"])

    def test_already_deduped_is_skipped(self):
        with _tmp_dir() as d:
            raw = d / "raw"
            deduped = d / "deduped"
            raw.mkdir()
            deduped.mkdir()
            (raw / "batch.json").write_text(json.dumps([{"contact_name": "Jane"}]))
            (deduped / "batch.json").write_text(json.dumps([{"already": "done"}]))
            dedup.dedup_file(raw / "batch.json", deduped)
            out = json.loads((deduped / "batch.json").read_text())
            self.assertEqual(out, [{"already": "done"}])

    def test_malformed_json_is_skipped_no_output_written(self):
        with _tmp_dir() as d:
            raw = d / "raw"
            deduped = d / "deduped"
            raw.mkdir()
            deduped.mkdir()
            (raw / "bad.json").write_text("{not valid json")
            dedup.dedup_file(raw / "bad.json", deduped)
            self.assertFalse((deduped / "bad.json").exists())

    @patch("dedup.crm.search_by_name", return_value=[])
    def test_single_object_wrapped_in_list(self, mock_search):
        with _tmp_dir() as d:
            raw = d / "raw"
            deduped = d / "deduped"
            raw.mkdir()
            deduped.mkdir()
            (raw / "one.json").write_text(json.dumps({"contact_name": "Solo Lead"}))
            dedup.dedup_file(raw / "one.json", deduped)
            out = json.loads((deduped / "one.json").read_text())
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["contact_name"], "Solo Lead")


class TestRun(unittest.TestCase):
    @patch("dedup.crm.search_by_name", return_value=[])
    def test_creates_deduped_dir_and_processes_all_raw_files(self, mock_search):
        with _tmp_dir() as d:
            raw = d / "raw"
            raw.mkdir()
            (raw / "a.json").write_text(json.dumps([{"contact_name": "A"}]))
            (raw / "b.json").write_text(json.dumps([{"contact_name": "B"}]))
            deduped = d / "deduped"
            self.assertFalse(deduped.exists())
            dedup.run(raw, deduped)
            self.assertTrue(deduped.exists())
            self.assertTrue((deduped / "a.json").exists())
            self.assertTrue((deduped / "b.json").exists())

    @patch("dedup.crm.search_by_name", return_value=[])
    def test_empty_raw_dir_no_error(self, mock_search):
        with _tmp_dir() as d:
            raw = d / "raw"
            raw.mkdir()
            deduped = d / "deduped"
            dedup.run(raw, deduped)
            self.assertTrue(deduped.exists())


if __name__ == "__main__":
    unittest.main()
