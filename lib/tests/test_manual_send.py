"""Unit tests for lib/manual_send.py — the copy-paste packet renderer.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import manual_send as ms  # noqa: E402

TOUCH_1 = {
    "lead_id": "lead-001", "contact_id": "", "touch_number": 1, "channel": "email",
    "scheduled_date": "2026-09-22", "to": "sam@example-prospect.com", "subject": "A Monday that isn't flat",
    "body": "Hi Sam,\n\nOne line per paragraph already.\n\nJane", "from_name": "Jane Founder",
    "recipient_tz": "America/Chicago",
}
TOUCH_3 = {**TOUCH_1, "touch_number": 3, "channel": "linkedin", "scheduled_date": "2026-10-01",
           "subject": "", "body": "Sam — fellow Springfielder, would love to connect."}
WRAPPED = {**TOUCH_1, "touch_number": 2, "scheduled_date": "2026-09-26",
           "body": ("Following up on a thought from last week about how a team gets\n"
                    "unstuck when the meeting energy drops and nobody wants to be the\n"
                    "one who speaks first, which happens more than people admit.")}
CONTACT = {
    "email": "sam@example-prospect.com", "contact_name": "Sam Example", "company_name": "Example Prospect Inc",
    "contact_title": "Head of People", "linkedin_url": "https://www.linkedin.com/in/sam-example",
    "contact_location": "Springfield, Illinois", "metro_match": "contact", "icp_segment": "people-team",
    "icp_rationale": "Springfield HQ, 400 staff, People team of 6", "signal": "new Head of People (2026-08)",
}


def _write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


class LoadAndGroup(unittest.TestCase):
    def test_loads_and_groups_sorted_by_touch_number(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root / "sends/queue/a-t2.json", WRAPPED)
            _write(root / "sends/linkedin/a-t3.json", TOUCH_3)
            _write(root / "sends/queue/a-t1.json", TOUCH_1)
            touches = ms.load_touches([root / "sends/queue/a-t2.json", root / "sends/linkedin/a-t3.json",
                                       root / "sends/queue/a-t1.json", root / "sends/queue/missing.json"])
            grouped = ms.group_by_lead(touches)
            self.assertEqual(list(grouped), ["lead-001"])
            self.assertEqual([t["touch_number"] for t in grouped["lead-001"]], [1, 2, 3])

    def test_missing_required_key_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            _write(p, {"lead_id": "x", "to": "x@y.com"})
            with self.assertRaises(ValueError):
                ms.load_touches([p])


class Rendering(unittest.TestCase):
    def test_checkbox_line_format_is_the_one_lead_issues_parses(self):
        block = ms.render_touch_block(TOUCH_1, CONTACT, warn=lambda *_: None)
        self.assertTrue(block.startswith("- [ ] Touch 1 — email — send on or after 2026-09-22"))
        self.assertIn("**Subject:** A Monday that isn't flat", block)
        self.assertIn("```text", block)
        self.assertIn("  Hi Sam,", block)

    def test_linkedin_block_points_at_profile_and_own_account(self):
        block = ms.render_touch_block(TOUCH_3, CONTACT, warn=lambda *_: None)
        self.assertIn("Touch 3 — linkedin — send on or after 2026-10-01", block)
        self.assertIn(CONTACT["linkedin_url"], block)
        self.assertIn("Jane Founder's own LinkedIn profile", block)
        self.assertNotIn("**Subject:**", block)

    def test_hard_wrapped_body_is_unwrapped_and_warned(self):
        warnings = []
        block = ms.render_touch_block(WRAPPED, CONTACT, warn=warnings.append)
        self.assertEqual(len(warnings), 1)
        self.assertIn("hard-wrapped", warnings[0])
        # The three fill-wrapped lines collapse into one paragraph line.
        body_lines = [line for line in block.splitlines() if line.startswith("  Following")]
        self.assertEqual(len(body_lines), 1)
        self.assertIn("more than people admit.", body_lines[0])

    def test_issue_title_and_body(self):
        self.assertEqual(ms.issue_title("lead-001", CONTACT), "Lead: Sam Example — Example Prospect Inc [lead-001]")
        body = ms.render_issue_body("lead-001", [TOUCH_1, TOUCH_3], CONTACT, warn=lambda *_: None)
        self.assertIn("**Email:** sam@example-prospect.com", body)
        self.assertIn("**Why now:** new Head of People (2026-08)", body)
        self.assertIn("`status:do-not-contact`", body)
        self.assertEqual(body.count("- [ ] Touch"), 2)

    def test_packet_covers_every_lead_and_touch(self):
        other = {**TOUCH_1, "lead_id": "lead-002", "to": "kim@another.example"}
        grouped = ms.group_by_lead([TOUCH_1, TOUCH_3, other])
        contacts = {CONTACT["email"]: CONTACT}
        packet = ms.render_packet(grouped, contacts, "2026-09-20", warn=lambda *_: None)
        self.assertIn("# Send packet — 2026-09-20", packet)
        self.assertIn("2 lead(s), 3 touch(es)", packet)
        self.assertIn("## Sam Example — Example Prospect Inc [lead-001]", packet)
        self.assertIn("## Unknown contact — unknown company [lead-002]", packet)  # no enriched record
        self.assertEqual(packet.count("- [ ] Touch"), 3)


class Cli(unittest.TestCase):
    def test_packet_command_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root / "sends/queue/a-t1.json", TOUCH_1)
            _write(root / "leads/enriched/2026-09-20.json", [CONTACT])
            out = root / "sends/manual/2026-09-20-send-packet.md"
            rc = ms.main(["packet", "--files", str(root / "sends/queue/a-t1.json"), "--out", str(out),
                          "--enriched-dir", str(root / "leads/enriched"), "--today", "2026-09-20"])
            self.assertEqual(rc, 0)
            self.assertIn("Sam Example", out.read_text())

    def test_packet_command_with_no_files_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "packet.md"
            self.assertEqual(ms.main(["packet", "--files", "--out", str(out)]), 0)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
