import contextlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import validate_data as vd  # noqa: E402

LEAD_RAW_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["company_name"],
    "additionalProperties": True,
    "properties": {"company_name": {"type": "string"}},
}

SEND_TOUCH_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["lead_id", "to"],
    "additionalProperties": True,
    "properties": {"lead_id": {"type": "string"}, "to": {"type": "string"}},
}


@contextlib.contextmanager
def _tmp_dir():
    p = Path(tempfile.mkdtemp())
    try:
        yield p
    finally:
        shutil.rmtree(p, ignore_errors=True)


def _write(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj))


def _make_root_with_schemas(root: Path, schemas: dict) -> None:
    for name, schema in schemas.items():
        _write(root / "schemas" / f"{name}.schema.json", schema)


class TestLoad(unittest.TestCase):
    def test_valid_json(self):
        with _tmp_dir() as d:
            p = d / "x.json"
            _write(p, {"a": 1})
            inst, err = vd.load(p)
            self.assertEqual(inst, {"a": 1})
            self.assertIsNone(err)

    def test_unparseable_json(self):
        with _tmp_dir() as d:
            p = d / "x.json"
            p.write_text("{not json")
            inst, err = vd.load(p)
            self.assertIsNone(inst)
            self.assertIn("unparseable JSON", err)


class TestLoadJsonl(unittest.TestCase):
    def test_valid_lines(self):
        with _tmp_dir() as d:
            p = d / "x.jsonl"
            p.write_text('{"a": 1}\n{"a": 2}\n\n{"a": 3}\n')
            records, err = vd.load_jsonl(p)
            self.assertIsNone(err)
            self.assertEqual(records, [{"a": 1}, {"a": 2}, {"a": 3}])

    def test_unparseable_line(self):
        with _tmp_dir() as d:
            p = d / "x.jsonl"
            p.write_text('{"a": 1}\nnot json\n')
            records, err = vd.load_jsonl(p)
            self.assertIsNone(records)
            self.assertIn("unparseable JSONL", err)


class TestLoadSchemas(unittest.TestCase):
    def test_valid_schema_loaded(self):
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"lead-raw": LEAD_RAW_SCHEMA})
            schemas, failures = vd.load_schemas(d / "schemas")
            self.assertEqual(failures, [])
            self.assertIn("lead-raw", schemas)

    def test_invalid_schema_reported(self):
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"broken": {"type": "not-a-real-type"}})
            schemas, failures = vd.load_schemas(d / "schemas")
            self.assertEqual(schemas, {})
            self.assertIn("invalid schema", failures[0])


class TestSchemaForPrefiltered(unittest.TestCase):
    def test_rejects_file(self):
        self.assertEqual(vd.schema_for_prefiltered(Path("leads/pre-filtered/2026-01-01-rejects.json")), "lead-reject")

    def test_passed_file(self):
        self.assertEqual(vd.schema_for_prefiltered(Path("leads/pre-filtered/2026-01-01.json")), "lead-pre-filtered")


class TestCheckArrayFile(unittest.TestCase):
    def test_each_element_validated(self):
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"lead-raw": LEAD_RAW_SCHEMA})
            schemas, _ = vd.load_schemas(d / "schemas")
            fp = d / "leads" / "raw" / "batch.json"
            _write(fp, [{"company_name": "Acme"}, {"no_name": True}])
            failures = vd.check_array_file(schemas, "lead-raw", fp)
            self.assertEqual(len(failures), 1)
            self.assertIn("[1]", failures[0])

    def test_not_an_array_reported(self):
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"lead-raw": LEAD_RAW_SCHEMA})
            schemas, _ = vd.load_schemas(d / "schemas")
            fp = d / "leads" / "raw" / "batch.json"
            _write(fp, {"company_name": "Acme"})
            failures = vd.check_array_file(schemas, "lead-raw", fp)
            self.assertEqual(len(failures), 1)
            self.assertIn("expected a JSON array", failures[0])


class TestCheckSingleFile(unittest.TestCase):
    def test_valid_passes(self):
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"send-touch": SEND_TOUCH_SCHEMA})
            schemas, _ = vd.load_schemas(d / "schemas")
            fp = d / "sends" / "queue" / "one.json"
            _write(fp, {"lead_id": "a", "to": "a@x.com"})
            self.assertEqual(vd.check_single_file(schemas, "send-touch", fp), [])

    def test_missing_required_flagged(self):
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"send-touch": SEND_TOUCH_SCHEMA})
            schemas, _ = vd.load_schemas(d / "schemas")
            fp = d / "sends" / "queue" / "one.json"
            _write(fp, {"lead_id": "a"})
            failures = vd.check_single_file(schemas, "send-touch", fp)
            self.assertEqual(len(failures), 1)


class TestCheckJsonlFile(unittest.TestCase):
    def test_each_line_validated(self):
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object", "required": ["email"], "properties": {"email": {"type": "string"}},
        }
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"suppression-line": schema})
            schemas, _ = vd.load_schemas(d / "schemas")
            fp = d / "suppression" / "list.jsonl"
            fp.parent.mkdir(parents=True)
            fp.write_text('{"email": "a@x.com"}\n{"no_email": true}\n')
            failures = vd.check_jsonl_file(schemas, "suppression-line", fp)
            self.assertEqual(len(failures), 1)
            self.assertIn(":2", failures[0])


class TestCheckPrScope(unittest.TestCase):
    def test_validates_only_queue_and_linkedin(self):
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"send-touch": SEND_TOUCH_SCHEMA})
            schemas, _ = vd.load_schemas(d / "schemas")
            _write(d / "sends" / "queue" / "a.json", {"lead_id": "a", "to": "a@x.com"})
            _write(d / "sends" / "linkedin" / "b.json", {"lead_id": "b"})  # missing "to"
            _write(d / "sends" / "rejected" / "c.json", {"lead_id": "c"})  # out of pr scope, ignored
            failures = vd.check_pr_scope(schemas, d)
            self.assertEqual(len(failures), 1)
            self.assertIn("b.json", failures[0])

    def test_missing_dirs_no_crash(self):
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"send-touch": SEND_TOUCH_SCHEMA})
            schemas, _ = vd.load_schemas(d / "schemas")
            self.assertEqual(vd.check_pr_scope(schemas, d), [])


class TestCheckFullScope(unittest.TestCase):
    def _schemas(self, root):
        specs = {
            "lead-raw": LEAD_RAW_SCHEMA,
            "lead-deduped": LEAD_RAW_SCHEMA,
            "lead-pre-filtered": LEAD_RAW_SCHEMA,
            "lead-reject": LEAD_RAW_SCHEMA,
            "lead-enriched": LEAD_RAW_SCHEMA,
            "critic-verdict": {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"},
            "stack-profile": {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"},
            "send-touch": SEND_TOUCH_SCHEMA,
            "send-touch-format-test": SEND_TOUCH_SCHEMA,
            "copy-verdict": {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"},
            "suppression-line": {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"},
            "daily-count": {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"},
        }
        _make_root_with_schemas(root, specs)
        schemas, _ = vd.load_schemas(root / "schemas")
        return schemas

    def test_prefiltered_split_by_filename(self):
        with _tmp_dir() as d:
            schemas = self._schemas(d)
            _write(d / "leads" / "pre-filtered" / "2026-01-01.json", [{"company_name": "Acme"}])
            _write(d / "leads" / "pre-filtered" / "2026-01-01-rejects.json", [{"company_name": "Beta"}])
            failures = vd.check_full_scope(schemas, d)
            self.assertEqual(failures, [])

    def test_bad_prefiltered_record_flagged(self):
        with _tmp_dir() as d:
            schemas = self._schemas(d)
            _write(d / "leads" / "pre-filtered" / "2026-01-01.json", [{"missing": "company_name"}])
            failures = vd.check_full_scope(schemas, d)
            self.assertEqual(len(failures), 1)

    def test_suppression_and_daily_count_only_checked_if_present(self):
        with _tmp_dir() as d:
            schemas = self._schemas(d)
            failures = vd.check_full_scope(schemas, d)
            self.assertEqual(failures, [])


class TestRunAndMain(unittest.TestCase):
    def test_run_pr_scope(self):
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"send-touch": SEND_TOUCH_SCHEMA})
            _write(d / "sends" / "queue" / "a.json", {"lead_id": "a", "to": "a@x.com"})
            failures, schema_count = vd.run(d, "pr")
            self.assertEqual(failures, [])
            self.assertEqual(schema_count, 1)

    def test_main_invalid_scope(self):
        self.assertEqual(vd.main(["validate_data.py", "bogus"]), 2)

    def test_main_exit_codes(self):
        with _tmp_dir() as d:
            _make_root_with_schemas(d, {"send-touch": SEND_TOUCH_SCHEMA})
            _write(d / "sends" / "queue" / "a.json", {"lead_id": "a", "to": "a@x.com"})
            self.assertEqual(vd.main(["validate_data.py", "pr", str(d)]), 0)
            _write(d / "sends" / "queue" / "b.json", {"lead_id": "b"})
            self.assertEqual(vd.main(["validate_data.py", "pr", str(d)]), 1)


if __name__ == "__main__":
    unittest.main()
