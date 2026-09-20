"""Unit tests for lib/lead_issues.py — GitHub Issues as the manual-send CRM layer.

Every gh call is patched; the CRM is the local JSONL backend pointed at a
temp dir; suppression and outcomes paths are temp files.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# crm.py annotates with requests.Response at import time; lib-tests.yml does
# not install requests (same stub convention as test_send_queue.py).
if "requests" not in sys.modules:
    sys.modules["requests"] = types.ModuleType("requests")
if not hasattr(sys.modules["requests"], "Response"):
    sys.modules["requests"].Response = type("Response", (), {})

import crm  # noqa: E402
import lead_issues as li  # noqa: E402
import suppression  # noqa: E402

TODAY = "2026-09-24"


def _issue(body: str, labels=("lead", "status:pending"), state="OPEN", number=42, lead_id="lead-001"):
    return {
        "number": number,
        "title": f"Lead: Sam Example — Example Prospect Inc [{lead_id}]",
        "body": body,
        "labels": [{"name": n} for n in labels],
        "state": state,
        "author": {"login": "listle"},
    }


BODY = """**How to work this lead:** ...

## Contact
**Name:** Sam Example
**Email:** sam@example-prospect.com
**Lead id:** `lead-001`

## Touches
- [x] Touch 1 — email — send on or after 2026-09-22
  **Subject:** Hi
- [ ] Touch 2 — email — send on or after 2026-09-26
- [X] Touch 3 — linkedin — send on or after 2026-10-01
"""


class Parsing(unittest.TestCase):
    def test_lead_id_from_title(self):
        self.assertEqual(li.lead_id_from_title("Lead: Sam — Co [lead-001]"), "lead-001")
        self.assertIsNone(li.lead_id_from_title("Some other issue"))

    def test_email_from_body(self):
        self.assertEqual(li.email_from_body(BODY), "sam@example-prospect.com")
        self.assertIsNone(li.email_from_body("**Email:** —"))

    def test_parse_checkboxes_reads_ticks_channels_dates(self):
        boxes = li.parse_checkboxes(BODY)
        self.assertEqual([(b["touch_number"], b["channel"], b["checked"]) for b in boxes],
                         [(1, "email", True), (2, "email", False), (3, "linkedin", True)])
        self.assertEqual(boxes[0]["send_after"], "2026-09-22")


class SyncIssue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.outcomes = root / "sends" / "outcomes.jsonl"
        self.env = patch.dict(os.environ, {
            "CRM_PROVIDER": "none",
            "SUPPRESSION_LIST_PATH": str(root / "suppression" / "list.jsonl"),
        })
        self.env.start()
        self._store = crm.LOCAL_STORE_DIR
        crm.LOCAL_STORE_DIR = root / "leads" / "crm-local"
        crm._backend_instance = None
        crm.upsert_contact({"email": "sam@example-prospect.com", "contact_name": "Sam Example",
                            "company_name": "Example Prospect Inc", "sequence_status": "pending", "suppressed": False})
        self.comments = []

    def tearDown(self):
        crm.LOCAL_STORE_DIR = self._store
        crm._backend_instance = None
        self.env.stop()
        self.tmp.cleanup()

    def _outcomes(self):
        return li.load_outcomes(self.outcomes)

    def test_ticks_become_touch_sent_and_enroll_the_contact(self):
        summary = li.sync_issue(_issue(BODY), today=TODAY, outcomes_path=self.outcomes)
        self.assertEqual(summary["lead_id"], "lead-001")
        self.assertEqual(sorted(summary["touches_recorded"]), [(1, "email"), (3, "linkedin")])
        events = [(o["event"], o.get("touch_number")) for o in self._outcomes()]
        self.assertEqual(sorted(events), [("touch_sent", 1), ("touch_sent", 3)])
        contact = crm.get_contact("sam@example-prospect.com")
        self.assertEqual(contact["sequence_status"], "enrolled")
        self.assertEqual(contact["sequence_enrolled_date"], TODAY)
        self.assertEqual(contact["last_touch_date"], TODAY)
        self.assertEqual(contact["last_touch_number"], 3)

    def test_sync_is_idempotent(self):
        li.sync_issue(_issue(BODY), today=TODAY, outcomes_path=self.outcomes)
        summary = li.sync_issue(_issue(BODY), today=TODAY, outcomes_path=self.outcomes)
        self.assertEqual(summary["touches_recorded"], [])
        self.assertEqual(len(self._outcomes()), 2)

    def test_replied_label_pauses_and_records_once(self):
        issue = _issue(BODY, labels=("lead", "status:replied"))
        li.sync_issue(issue, today=TODAY, outcomes_path=self.outcomes)
        li.sync_issue(issue, today=TODAY, outcomes_path=self.outcomes)
        contact = crm.get_contact("sam@example-prospect.com")
        self.assertEqual(contact["sequence_status"], "paused")
        self.assertTrue(contact["reply_received"])
        self.assertEqual([o["event"] for o in self._outcomes()].count("replied"), 1)

    def test_booked_and_no_response_complete_the_sequence(self):
        li.sync_issue(_issue(BODY, labels=("lead", "status:booked")), today=TODAY, outcomes_path=self.outcomes)
        self.assertEqual(crm.get_contact("sam@example-prospect.com")["sequence_status"], "completed")
        self.assertIn("booked", [o["event"] for o in self._outcomes()])
        li.sync_issue(_issue(BODY, labels=("lead", "status:no-response"), lead_id="lead-001"),
                      today=TODAY, outcomes_path=self.outcomes)
        self.assertIn("no_response", [o["event"] for o in self._outcomes()])

    def test_do_not_contact_rejects_suppresses_and_comments_once(self):
        issue = _issue(BODY, labels=("lead", "status:do-not-contact"))
        comment_fn = lambda repo, n, text: self.comments.append((repo, n, text))  # noqa: E731
        li.sync_issue(issue, today=TODAY, outcomes_path=self.outcomes, repo="o/r", comment_fn=comment_fn)
        li.sync_issue(issue, today=TODAY, outcomes_path=self.outcomes, repo="o/r", comment_fn=comment_fn)
        contact = crm.get_contact("sam@example-prospect.com")
        self.assertEqual(contact["sequence_status"], "rejected")
        self.assertTrue(contact["suppressed"])
        self.assertTrue(suppression.check("sam@example-prospect.com"))
        self.assertEqual(len(self.comments), 1)
        self.assertEqual([o["event"] for o in self._outcomes()].count("do_not_contact"), 1)

    def test_do_not_contact_wins_over_other_labels(self):
        issue = _issue(BODY, labels=("lead", "status:replied", "status:do-not-contact"))
        summary = li.sync_issue(issue, today=TODAY, outcomes_path=self.outcomes)
        self.assertEqual(summary["status"], "do_not_contact")

    def test_closed_without_status_records_a_note_only(self):
        issue = _issue(BODY.replace("[x]", "[ ]").replace("[X]", "[ ]"), labels=("lead",), state="CLOSED")
        summary = li.sync_issue(issue, today=TODAY, outcomes_path=self.outcomes)
        self.assertEqual(summary["status"], "closed_without_status")
        self.assertEqual([o["event"] for o in self._outcomes()], ["note"])
        self.assertEqual(crm.get_contact("sam@example-prospect.com")["sequence_status"], "pending")

    def test_title_without_lead_id_is_skipped(self):
        issue = _issue(BODY)
        issue["title"] = "Lead: Sam Example — Example Prospect Inc"
        summary = li.sync_issue(issue, today=TODAY, outcomes_path=self.outcomes)
        self.assertEqual(summary["skipped"], "no [lead_id] in title")
        self.assertEqual(self._outcomes(), [])

    def test_email_falls_back_to_queue_file(self):
        with tempfile.TemporaryDirectory() as d:
            q = Path(d) / "sends" / "queue"
            q.mkdir(parents=True)
            (q / "x.json").write_text(json.dumps({"lead_id": "lead-001", "to": "sam@example-prospect.com"}))
            body = BODY.replace("**Email:** sam@example-prospect.com\n", "")
            summary = li.sync_issue(_issue(body), today=TODAY, outcomes_path=self.outcomes, queue_dirs=(q,))
            self.assertIsNone(summary["skipped"])
            self.assertEqual(len(summary["touches_recorded"]), 2)


class CreateIssues(unittest.TestCase):
    def test_creates_one_issue_per_lead_and_skips_existing(self):
        touch = {
            "lead_id": "lead-001", "contact_id": "", "touch_number": 1, "channel": "email",
            "scheduled_date": "2026-09-22", "to": "sam@example-prospect.com", "subject": "Hi",
            "body": "Hi Sam", "from_name": "Jane Founder", "recipient_tz": "America/Chicago",
        }
        other = {**touch, "lead_id": "lead-002", "to": "kim@another.example"}
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "q").mkdir()
            (root / "q" / "a.json").write_text(json.dumps(touch))
            (root / "q" / "b.json").write_text(json.dumps(other))
            created_calls = []

            def fake_create(repo, title, body, labels):
                created_calls.append((title, labels))
                return "https://x/issues/8"

            with patch.object(li, "ensure_labels", lambda repo: None), \
                 patch.object(li, "existing_issues", lambda repo: {"lead-002": 7}), \
                 patch.object(li, "create_issue", fake_create):
                created = li.create_issues([root / "q" / "a.json", root / "q" / "b.json"], repo="o/r",
                                           enriched_dir=root / "none", warn=lambda *_: None)
            self.assertEqual([c["lead_id"] for c in created], ["lead-001"])
            self.assertEqual(created_calls[0][1], ["lead", "status:pending"])
            self.assertIn("[lead-001]", created_calls[0][0])


if __name__ == "__main__":
    unittest.main()
