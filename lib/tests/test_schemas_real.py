"""Validate representative lead records against the REAL schemas in schemas/.

The other tests use stub schemas. This one loads the actual files so a field
added to the pipeline (e.g. the metro/location fields, Apify source fields)
is proven to be accepted by every stage schema, and a typo in a schema file
fails CI instead of failing silently in a bot push.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import validate_data as vd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMAS, LOAD_FAILURES = vd.load_schemas(ROOT / "schemas")

# Synthetic contact — never a real prospect.
BASE = {
    "company_name": "Example Widgets Co",
    "website": "example-widgets.test",
    "employee_count": 240,
    "industry": "professional services",
    "contact_name": "Sam Example",
    "contact_title": "Director of Operations",
    "linkedin_url": "https://www.linkedin.com/in/sam-example",
    "icp_segment": "professional services (law, accounting, agencies, consulting)",
    "icp_rationale": "Operations lead at a mid-size local employer.",
    "country_code": "US",
    "source": "apify:linkedin",
}

GEO = {
    "contact_location": "Springfield, Illinois, United States",
    "company_hq_location": "Decatur, Illinois, United States",
    "metro_match": "contact",
    "metro_evidence": "apify:location",
}

SOURCE_META = {
    "signal": "hiring_people_function",
    "evidence_url": "https://example-widgets.test/careers/people-ops",
    "source_actor": "harvestapi/linkedin-profile-search",
    "source_run_id": "run_abc123",
    "source_id": "sam-example",
}


def _errs(name, rec):
    return vd.validate_instance(SCHEMAS, name, rec, name)


class TestSchemasLoad(unittest.TestCase):
    def test_all_schema_files_are_valid(self):
        self.assertEqual(LOAD_FAILURES, [])
        for required in ("lead-raw", "lead-deduped", "lead-pre-filtered", "lead-reject", "lead-enriched"):
            self.assertIn(required, SCHEMAS)


class TestGeoFieldsAccepted(unittest.TestCase):
    def test_raw_with_geo(self):
        self.assertEqual(_errs("lead-raw", {**BASE, **GEO}), [])

    def test_deduped_with_geo(self):
        self.assertEqual(_errs("lead-deduped", {**BASE, **GEO, "prior_contact": False}), [])

    def test_pre_filtered_with_geo_and_flag(self):
        rec = {
            **BASE, **GEO,
            "prior_contact": False, "eu_flagged": False, "mql_score": 40,
            "pre_filter_passed": True, "pre_filter_date": "2026-09-20",
            "metro_match": "unknown", "location_flag": "unknown_needs_review",
        }
        self.assertEqual(_errs("lead-pre-filtered", rec), [])

    def test_reject_outside_metro(self):
        rec = {
            **BASE, **GEO, "metro_match": "none",
            "prior_contact": False, "pre_filter_passed": False,
            "pre_filter_date": "2026-09-20",
            "reject_reason": "outside_metro: Dallas, Texas, United States / Dallas, Texas, United States",
        }
        self.assertEqual(_errs("lead-reject", rec), [])

    def test_enriched_with_geo(self):
        rec = {
            **BASE, **GEO, "metro_match": "local_office",
            "metro_evidence": "https://example-widgets.test/careers/springfield",
            "email": "sam@example-widgets.test", "email_verified": True,
            "email_status": "deliverable", "email_source": "prospeo",
        }
        self.assertEqual(_errs("lead-enriched", rec), [])

    def test_bad_metro_match_rejected(self):
        errs = _errs("lead-raw", {**BASE, **GEO, "metro_match": "nearby"})
        self.assertTrue(errs and "metro_match" in errs[0])


class TestSourceMetaAccepted(unittest.TestCase):
    def test_raw_with_source_meta(self):
        self.assertEqual(_errs("lead-raw", {**BASE, **GEO, **SOURCE_META}), [])

    def test_enriched_with_source_meta(self):
        rec = {
            **BASE, **GEO, **SOURCE_META,
            "email": "", "email_verified": False, "email_status": "not_found",
        }
        self.assertEqual(_errs("lead-enriched", rec), [])


class TestCompanyLead(unittest.TestCase):
    def test_company_lead_minimal(self):
        rec = {
            "company_name": "Example Widgets Co",
            "source": "apify:google_maps",
            "source_id": "ChIJexample",
            "signal": "local_employer",
            "discovered_date": "2026-09-20",
        }
        self.assertEqual(_errs("company-lead", rec), [])

    def test_company_lead_full(self):
        rec = {
            "company_name": "Example Widgets Co",
            "website": "example-widgets.test",
            "address": "100 Example St, Springfield, IL 62701",
            "city": "Springfield",
            "region": "Texas",
            "country_code": "US",
            "category": "Software company",
            "employee_count_hint": 250,
            "linkedin_company_url": "https://www.linkedin.com/company/example-widgets",
            "evidence_url": "https://example-widgets.test/careers",
            "signal": "hiring_people_function",
            "signal_date": "2026-09-15",
            "posting_title": "People Operations Manager",
            "people_searched_date": "2026-09-20",
            "metro_match": "company_hq",
            "source": "apify:job_postings",
            "source_actor": "misceres/indeed-scraper",
            "source_run_id": "run_def456",
            "source_id": "indeed-123",
            "discovered_date": "2026-09-20",
        }
        self.assertEqual(_errs("company-lead", rec), [])


if __name__ == "__main__":
    unittest.main()
