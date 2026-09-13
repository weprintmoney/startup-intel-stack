"""Outcome pass/fail logic for lib/upsert_report.py.

On 2026-09-06 dedup-review.yml exited 0 while 24 of 24 CRM upserts failed
— these cases pin the fix: a healthy run stays green, a total-failure run
(the incident shape) fails loud, a schema-not-provisioned-yet run (expected
pre-sales-ops#45) stays green, and a single read-back mismatch fails loud
even when the write itself reported success.

Run: python -m unittest discover -s lib/tests -p "test_*.py"
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from upsert_report import classify, decide, new_summary, render_markdown  # noqa: E402


class Classify(unittest.TestCase):
    def test_cannot_find_attribute_is_schema_unprovisioned(self):
        self.assertEqual(classify("Cannot find attribute with slug pain_point"), "schema_unprovisioned")

    def test_not_authorized_is_schema_unprovisioned(self):
        self.assertEqual(classify("403 not authorized to create attribute"), "schema_unprovisioned")

    def test_value_not_found_is_crm_error(self):
        self.assertEqual(classify("CRM API error 400: value_not_found: pre-seed"), "crm_error")

    def test_generic_error_is_crm_error(self):
        self.assertEqual(classify("CRM API error 429: rate limited"), "crm_error")


class AllPassStaysGreen(unittest.TestCase):
    def test_healthy_run_has_no_failure_reasons(self):
        summary = new_summary()
        summary["verdict_pass"] = 10
        summary["attempted"] = 10
        summary["upserted"] = 10
        summary["readback_ok"] = 10
        self.assertEqual(decide(summary), [])
        self.assertIn("PASS", render_markdown(summary))


class TotalFailureFailsLoud(unittest.TestCase):
    def test_24_of_24_value_not_found_fails(self):
        summary = new_summary()
        summary["verdict_pass"] = 24
        summary["attempted"] = 24
        summary["upserted"] = 0
        summary["errors"]["crm_error"] = 24
        summary["error_lines"] = [f"lead{i}@x.com: value_not_found: pre-seed" for i in range(24)]

        reasons = decide(summary)
        self.assertTrue(reasons)
        self.assertTrue(any("24" in r and "attempted" in r for r in reasons))
        self.assertTrue(any("24" in r and "CRM error" in r for r in reasons))

        rendered = render_markdown(summary)
        self.assertIn("FAIL", rendered)
        self.assertIn("value_not_found: pre-seed", rendered)


class SchemaUnprovisionedOnlyStaysGreen(unittest.TestCase):
    def test_every_upsert_hitting_the_infra_gap_does_not_fail_the_run(self):
        summary = new_summary()
        summary["verdict_pass"] = 24
        summary["skipped"]["schema_unprovisioned"] = 24
        # attempted stays 0 — classify() routed every exception to the
        # infra-gap bucket before it could count as an attempt.
        self.assertEqual(summary["attempted"], 0)
        self.assertEqual(summary["upserted"], 0)

        self.assertEqual(decide(summary), [])
        self.assertIn("PASS", render_markdown(summary))


class OneReadbackMismatchFailsLoud(unittest.TestCase):
    def test_single_mismatch_among_many_ok_still_fails(self):
        summary = new_summary()
        summary["verdict_pass"] = 5
        summary["attempted"] = 5
        summary["upserted"] = 5
        summary["readback_ok"] = 4
        summary["readback_mismatch"] = 1
        summary["error_lines"] = ["a@x.com: read-back mismatch (icp_segment='healthcare-ai' != 'finserv-ai')"]

        reasons = decide(summary)
        self.assertTrue(any("1" in r and "read-back mismatch" in r for r in reasons))
        self.assertIn("FAIL", render_markdown(summary))


if __name__ == "__main__":
    unittest.main()
