"""Unwrapping behaviour for lib/format_body.py.

A copy draft can ship with newlines filled at ~75 columns from a rich-text
editor, which reads as ragged mid-sentence breaks in plain-text email.
Unwrapping is easy to over-apply, so the
cases that must NOT change — signatures, list items, copy already written one
line per paragraph — are covered as carefully as the ones that must.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from format_body import unwrap_body  # noqa: E402


class JoinsFillWrappedProse(unittest.TestCase):
    def test_joins_a_filled_paragraph_into_one_line(self):
        body = (
            "Shane — ClaimSearch pools structured claim fields from ~95% of the US P&C\n"
            "market, but the photo and document embeddings that would catch the same\n"
            "evidence reused across carriers stay siloed at each carrier."
        )
        self.assertEqual(
            unwrap_body(body),
            "Shane — ClaimSearch pools structured claim fields from ~95% of the US P&C "
            "market, but the photo and document embeddings that would catch the same "
            "evidence reused across carriers stay siloed at each carrier.",
        )

    def test_keeps_paragraph_breaks(self):
        body = (
            "A filled paragraph whose first line runs to roughly seventy columns\n"
            "and then continues.\n"
            "\n"
            "A second filled paragraph that also runs out to about seventy odd\n"
            "columns before ending."
        )
        self.assertEqual(len(unwrap_body(body).split("\n\n")), 2)
        self.assertNotIn("\n", unwrap_body(body).split("\n\n")[0])


class LeavesDeliberateBreaksAlone(unittest.TestCase):
    def test_signature_block_survives(self):
        body = "Jamie\nFounder & CEO, Acme · acme.example.com"
        self.assertEqual(unwrap_body(body), body)

    def test_list_items_are_never_joined(self):
        body = (
            "- first bullet, long enough to look like a filled line at this width\n"
            "- second bullet, also long enough to look like a filled line here"
        )
        self.assertEqual(unwrap_body(body), body)

    def test_body_already_one_line_per_paragraph_is_untouched(self):
        body = (
            "A single long paragraph written as one line, the shape every queue file "
            "is supposed to be in, running well past any fill column.\n"
            "\n"
            "Jamie"
        )
        self.assertEqual(unwrap_body(body), body)

    def test_short_linkedin_note_is_untouched(self):
        body = "Hi Julien, sent you a note on the vector search post. Would love to connect.\n— Jamie"
        self.assertEqual(unwrap_body(body), body)


class Invariants(unittest.TestCase):
    def test_unwrapping_is_idempotent(self):
        body = (
            "A filled paragraph whose first line runs to roughly seventy columns\n"
            "and then stops.\n"
            "\n"
            "Jamie\n"
            "Founder & CEO, Acme · acme.example.com"
        )
        once = unwrap_body(body)
        self.assertEqual(unwrap_body(once), once)

    def test_no_words_are_lost_or_added(self):
        body = (
            "A filled paragraph whose first line runs to roughly seventy columns\n"
            "and then stops.\n"
            "\n"
            "Jamie"
        )
        self.assertEqual(unwrap_body(body).split(), body.split())

    def test_empty_body(self):
        self.assertEqual(unwrap_body(""), "")


if __name__ == "__main__":
    unittest.main()
