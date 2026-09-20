import contextlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sequence_enrollment as se  # noqa: E402


@contextlib.contextmanager
def _tmp_dir():
    p = Path(tempfile.mkdtemp())
    try:
        yield p
    finally:
        shutil.rmtree(p, ignore_errors=True)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


class TestVerdictsPath(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(se.verdicts_path("2026-09-12"), Path("sends/verdicts/2026-09-12.json"))


class TestLoadVerdicts(unittest.TestCase):
    def test_missing_file_returns_none(self):
        with _tmp_dir() as d:
            self.assertIsNone(se.load_verdicts(d / "nope.json"))

    def test_existing_file_parsed(self):
        with _tmp_dir() as d:
            vfile = d / "verdicts.json"
            _write_json(vfile, [{"lead_id": "1", "decision": "PASS"}])
            self.assertEqual(se.load_verdicts(vfile), [{"lead_id": "1", "decision": "PASS"}])


class TestFailedLeadIds(unittest.TestCase):
    def test_only_non_pass_with_lead_id(self):
        verdicts = [
            {"lead_id": "a", "decision": "PASS"},
            {"lead_id": "b", "decision": "FAIL"},
            {"lead_id": "", "decision": "FAIL"},
            {"decision": "FAIL"},
        ]
        self.assertEqual(se.failed_lead_ids(verdicts), {"b"})

    def test_empty_verdicts_empty_set(self):
        self.assertEqual(se.failed_lead_ids([]), set())


class TestMoveFailedDrafts(unittest.TestCase):
    def test_moves_matching_files(self):
        with _tmp_dir() as d:
            queue = d / "queue"
            rejected = d / "rejected"
            _write_json(queue / "a.json", {"lead_id": "a"})
            _write_json(queue / "b.json", {"lead_id": "b"})
            moved = se.move_failed_drafts([queue], {"b"}, rejected)
            self.assertEqual(moved, 1)
            self.assertTrue((rejected / "b.json").exists())
            self.assertTrue((queue / "a.json").exists())
            self.assertFalse((queue / "b.json").exists())

    def test_nonexistent_dir_skipped(self):
        with _tmp_dir() as d:
            moved = se.move_failed_drafts([d / "nope"], {"x"}, d / "rejected")
            self.assertEqual(moved, 0)
            self.assertFalse((d / "rejected").exists())

    def test_unparseable_file_skipped_not_moved(self):
        with _tmp_dir() as d:
            queue = d / "queue"
            queue.mkdir(parents=True)
            (queue / "bad.json").write_text("{not json")
            moved = se.move_failed_drafts([queue], {"whatever"}, d / "rejected")
            self.assertEqual(moved, 0)
            self.assertTrue((queue / "bad.json").exists())

    def test_multiple_dirs(self):
        with _tmp_dir() as d:
            queue = d / "queue"
            linkedin = d / "linkedin"
            rejected = d / "rejected"
            _write_json(queue / "a.json", {"lead_id": "a"})
            _write_json(linkedin / "c.json", {"lead_id": "c"})
            moved = se.move_failed_drafts([queue, linkedin], {"a", "c"}, rejected)
            self.assertEqual(moved, 2)
            self.assertTrue((rejected / "a.json").exists())
            self.assertTrue((rejected / "c.json").exists())


class TestUnverdictedEmailLeads(unittest.TestCase):
    def test_finds_leads_missing_from_scored(self):
        with _tmp_dir() as d:
            queue = d / "queue"
            _write_json(queue / "a.json", {"lead_id": "a"})
            _write_json(queue / "b.json", {"lead_id": "b"})
            result = se.unverdicted_email_leads(queue, {"a"})
            self.assertEqual(result, ["b"])

    def test_no_queue_dir_returns_empty(self):
        with _tmp_dir() as d:
            self.assertEqual(se.unverdicted_email_leads(d / "nope", {"a"}), [])

    def test_unparseable_file_ignored(self):
        with _tmp_dir() as d:
            queue = d / "queue"
            queue.mkdir()
            (queue / "bad.json").write_text("{not json")
            self.assertEqual(se.unverdicted_email_leads(queue, set()), [])

    def test_all_scored_returns_empty(self):
        with _tmp_dir() as d:
            queue = d / "queue"
            _write_json(queue / "a.json", {"lead_id": "a"})
            self.assertEqual(se.unverdicted_email_leads(queue, {"a"}), [])


class TestBuildPrBody(unittest.TestCase):
    def test_contains_table_and_date(self):
        verdicts = [
            {"lead_id": "a", "decision": "PASS", "lead_email": "a@x.com", "normalized_score": 95},
            {
                "lead_id": "b", "decision": "FAIL", "lead_email": "b@x.com", "normalized_score": 40,
                "failing_criteria": ["tone"], "hard_block_hits": ["claim"],
            },
        ]
        body = se.build_pr_body(verdicts, "2026-09-12")
        self.assertIn("2026-09-12", body)
        self.assertIn("a@x.com", body)
        self.assertIn("b@x.com", body)
        self.assertIn("tone, claim", body)
        self.assertIn("✅ PASS", body)
        self.assertIn("❌ FAIL", body)
        self.assertIn("sends/rejected/", body)

    def test_no_failing_criteria_renders_dash(self):
        verdicts = [{"lead_id": "a", "decision": "PASS", "lead_email": "a@x.com", "normalized_score": 95}]
        body = se.build_pr_body(verdicts, "2026-09-12")
        self.assertIn("| ✅ PASS | a@x.com | 95/100 | — |", body)

    def test_no_leading_whitespace_on_any_line(self):
        verdicts = [{"lead_id": "a", "decision": "PASS", "lead_email": "a@x.com", "normalized_score": 95}]
        body = se.build_pr_body(verdicts, "2026-09-12")
        for line in body.splitlines():
            self.assertEqual(line, line.lstrip())


class TestRun(unittest.TestCase):
    def test_missing_verdicts_file_returns_1_and_writes_no_pr_body(self):
        with _tmp_dir() as d:
            rc = se.run(
                queue_dir=d / "queue", linkedin_dir=d / "linkedin", rejected_dir=d / "rejected",
                vfile=d / "verdicts.json", today="2026-09-12", pr_body_path=d / "pr-body.md",
            )
            self.assertEqual(rc, 1)
            self.assertFalse((d / "pr-body.md").exists())

    def test_unverdicted_lead_returns_1_after_moving_failed(self):
        with _tmp_dir() as d:
            queue = d / "queue"
            _write_json(queue / "failed.json", {"lead_id": "failed"})
            _write_json(queue / "unscored.json", {"lead_id": "unscored"})
            _write_json(d / "verdicts.json", [{"lead_id": "failed", "decision": "FAIL"}])

            rc = se.run(
                queue_dir=queue, linkedin_dir=d / "linkedin", rejected_dir=d / "rejected",
                vfile=d / "verdicts.json", today="2026-09-12", pr_body_path=d / "pr-body.md",
            )
            self.assertEqual(rc, 1)
            self.assertFalse((d / "pr-body.md").exists())
            self.assertTrue((d / "rejected" / "failed.json").exists())

    def test_success_case_writes_pr_body_and_moves_failed(self):
        with _tmp_dir() as d:
            queue = d / "queue"
            linkedin = d / "linkedin"
            _write_json(queue / "pass.json", {"lead_id": "pass"})
            _write_json(queue / "fail.json", {"lead_id": "fail"})
            _write_json(linkedin / "note.json", {"lead_id": "li-note"})
            _write_json(
                d / "verdicts.json",
                [
                    {"lead_id": "pass", "decision": "PASS", "lead_email": "p@x.com", "normalized_score": 90},
                    {"lead_id": "fail", "decision": "FAIL", "lead_email": "f@x.com", "normalized_score": 20},
                ],
            )

            rc = se.run(
                queue_dir=queue, linkedin_dir=linkedin, rejected_dir=d / "rejected",
                vfile=d / "verdicts.json", today="2026-09-12", pr_body_path=d / "pr-body.md",
            )
            self.assertEqual(rc, 0)
            self.assertTrue((d / "rejected" / "fail.json").exists())
            self.assertTrue((queue / "pass.json").exists())
            self.assertTrue((linkedin / "note.json").exists())
            body = (d / "pr-body.md").read_text()
            self.assertIn("p@x.com", body)
            self.assertIn("2026-09-12", body)

    def test_linkedin_only_batch_no_email_drafts_still_succeeds(self):
        with _tmp_dir() as d:
            linkedin = d / "linkedin"
            _write_json(linkedin / "note.json", {"lead_id": "li-note"})
            _write_json(d / "verdicts.json", [])

            rc = se.run(
                queue_dir=d / "queue", linkedin_dir=linkedin, rejected_dir=d / "rejected",
                vfile=d / "verdicts.json", today="2026-09-12", pr_body_path=d / "pr-body.md",
            )
            self.assertEqual(rc, 0)
            self.assertTrue((linkedin / "note.json").exists())


if __name__ == "__main__":
    unittest.main()
