#!/usr/bin/env python3
"""Unit tests for scripts/validate-state.py (run by schema-validate.yml)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("vs", HERE / "validate-state.py")
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)


QUEUE_CLAIM_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["id", "status"],
    "properties": {"id": {"type": "string"}, "status": {"type": "string"}},
}

DEPENDABOT_REPOS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
}

IMPL_REPOS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
}

QUEUE_CLAIM_SCHEMA_WITH_ENUM = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["id", "status"],
    "properties": {
        "id": {"type": "string"},
        "status": {"enum": ["claimed", "spec-pending", "spec-clarify-pending", "merged", "abandoned"]},
    },
}

SAMPLE_TRANSITIONS = {
    "claimed": ["spec-pending", "spec-clarify-pending", "abandoned"],
    "spec-clarify-pending": ["spec-pending", "spec-clarify-pending", "abandoned"],
    "spec-pending": ["merged", "abandoned"],
    "merged": [],
    "abandoned": [],
}


def write(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj))


def make_root(tmp: Path, *, schemas: dict[str, dict] | None = None) -> Path:
    for name, schema in (schemas or {}).items():
        write(tmp / "schemas" / f"{name}.schema.json", schema)
    return tmp


class TestLoad(unittest.TestCase):
    def test_valid_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            write(p, {"a": 1})
            inst, err = vs.load(p)
            self.assertEqual(inst, {"a": 1})
            self.assertIsNone(err)

    def test_unparseable_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            p.write_text("{not json")
            inst, err = vs.load(p)
            self.assertIsNone(inst)
            self.assertIn("unparseable JSON", err)


class TestLoadSchemas(unittest.TestCase):
    def test_valid_schema_loaded(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d), schemas={"queue-claim": QUEUE_CLAIM_SCHEMA})
            schemas, failures = vs.load_schemas(root / "schemas")
            self.assertEqual(failures, [])
            self.assertIn("queue-claim", schemas)

    def test_invalid_schema_reported(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d), schemas={"broken": {"type": "not-a-real-type"}})
            schemas, failures = vs.load_schemas(root / "schemas")
            self.assertEqual(schemas, {})
            self.assertEqual(len(failures), 1)
            self.assertIn("invalid schema", failures[0])

    def test_unparseable_schema_file_reported(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "schemas").mkdir()
            (root / "schemas" / "bad.schema.json").write_text("{not json")
            schemas, failures = vs.load_schemas(root / "schemas")
            self.assertEqual(schemas, {})
            self.assertIn("unparseable JSON", failures[0])


class TestCheckQueue(unittest.TestCase):
    def _schemas(self, tmp):
        root = make_root(tmp, schemas={"queue-claim": QUEUE_CLAIM_SCHEMA})
        schemas, _ = vs.load_schemas(root / "schemas")
        return schemas

    def test_missing_file_reported_as_unparseable(self):
        # Matches the original heredoc: Path.read_text() on a missing file
        # raises, and the bare except treats it the same as malformed JSON.
        # In practice state/queue.json always exists in this repo, so this
        # documents a pre-existing quirk rather than a designed behavior.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            failures = vs.check_queue(schemas, root / "state" / "queue.json", {})
            self.assertEqual(len(failures), 1)
            self.assertIn("unparseable JSON", failures[0])

    def test_wrong_types_short_circuits(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            write(root / "state" / "queue.json", {"wip_cap": "2", "claims": []})
            failures = vs.check_queue(schemas, root / "state" / "queue.json", {})
            self.assertEqual(len(failures), 1)
            self.assertIn("must have integer wip_cap and array claims", failures[0])

    def test_active_claims_exceed_cap(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            claims = [{"id": "a", "status": "in-progress"}, {"id": "b", "status": "in-progress"}]
            write(root / "state" / "queue.json", {"wip_cap": 1, "claims": claims})
            failures = vs.check_queue(schemas, root / "state" / "queue.json", SAMPLE_TRANSITIONS)
            self.assertTrue(any("exceed wip_cap" in f for f in failures))

    def test_terminal_statuses_excluded_from_active_count(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            claims = [
                {"id": "a", "status": "merged"},
                {"id": "b", "status": "abandoned"},
                {"id": "c", "status": "spec-clarify-pending"},
            ]
            write(root / "state" / "queue.json", {"wip_cap": 0, "claims": claims})
            failures = vs.check_queue(schemas, root / "state" / "queue.json", SAMPLE_TRANSITIONS)
            self.assertFalse(any("exceed wip_cap" in f for f in failures))

    def test_each_claim_validated_against_schema(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            claims = [{"id": "a"}]  # missing required "status"
            write(root / "state" / "queue.json", {"wip_cap": 5, "claims": claims})
            failures = vs.check_queue(schemas, root / "state" / "queue.json", {})
            self.assertTrue(any("claims[0]" in f for f in failures))

    def test_two_rows_for_one_issue_repo_key_flagged(self):
        # Intake re-claimed after an abandon by appending
        # a second row for the same (issue, impl_repo); update-claim.sh then
        # read both statuses and rejected every transition as illegal.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            claims = [
                {"id": "a", "issue": 7, "impl_repo": "example-org/example-app-sdk-py", "status": "abandoned"},
                {"id": "b", "issue": 7, "impl_repo": "example-org/example-app-sdk-py", "status": "claimed"},
            ]
            write(root / "state" / "queue.json", {"wip_cap": 5, "claims": claims})
            failures = vs.check_queue(schemas, root / "state" / "queue.json", SAMPLE_TRANSITIONS)
            self.assertTrue(any("2 rows for claim #7 in example-org/example-app-sdk-py" in f for f in failures))

    def test_fan_out_across_repos_is_not_a_duplicate(self):
        # One ticket, one claim per implementation repo (py + js) is the
        # designed shape, not a duplicate.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            claims = [
                {"id": "a", "issue": 7, "impl_repo": "example-org/example-app-sdk-py", "status": "claimed"},
                {"id": "b", "issue": 7, "impl_repo": "example-org/example-app-sdk-js", "status": "claimed"},
            ]
            write(root / "state" / "queue.json", {"wip_cap": 5, "claims": claims})
            failures = vs.check_queue(schemas, root / "state" / "queue.json", SAMPLE_TRANSITIONS)
            self.assertFalse(any("rows for claim" in f for f in failures))


class TestCheckDependabotRepos(unittest.TestCase):
    def _schemas(self, tmp):
        root = make_root(tmp, schemas={"dependabot-repos": DEPENDABOT_REPOS_SCHEMA})
        schemas, _ = vs.load_schemas(root / "schemas")
        return schemas

    def test_out_not_in_pool_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            path = root / "state" / "dependabot-repos.json"
            write(path, {"reviewers": {"pool": ["alice"], "out": ["bob"]}})
            failures = vs.check_dependabot_repos(schemas, path)
            self.assertTrue(any("not in reviewers.pool" in f for f in failures))

    def test_everyone_out_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            path = root / "state" / "dependabot-repos.json"
            write(path, {"reviewers": {"pool": ["alice"], "out": ["alice"]}})
            failures = vs.check_dependabot_repos(schemas, path)
            self.assertTrue(any("no active member" in f for f in failures))

    def test_healthy_pool_no_failures(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            path = root / "state" / "dependabot-repos.json"
            write(path, {"reviewers": {"pool": ["alice", "bob"], "out": ["bob"]}})
            failures = vs.check_dependabot_repos(schemas, path)
            self.assertEqual(failures, [])


class TestCheckImplRepos(unittest.TestCase):
    def _schemas(self, tmp):
        root = make_root(tmp, schemas={"impl-repos": IMPL_REPOS_SCHEMA})
        schemas, _ = vs.load_schemas(root / "schemas")
        return schemas

    def test_registered_without_guard_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            (root / "guards").mkdir()
            path = root / "state" / "impl-repos.json"
            write(path, {"repos": {"example-app-core": {}}})
            failures = vs.check_impl_repos(schemas, path, root / "guards")
            self.assertTrue(any("is registered but has no guards/example-app-core.paths" in f for f in failures))

    def test_guard_without_registration_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            (root / "guards").mkdir()
            (root / "guards" / "orphan-repo.paths").write_text("")
            path = root / "state" / "impl-repos.json"
            write(path, {"repos": {}})
            failures = vs.check_impl_repos(schemas, path, root / "guards")
            self.assertTrue(any("guards/orphan-repo.paths: no entry in" in f for f in failures))

    def test_symmetric_match_no_failures(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            schemas = self._schemas(root)
            (root / "guards").mkdir()
            (root / "guards" / "example-app-core.paths").write_text("")
            path = root / "state" / "impl-repos.json"
            write(path, {"repos": {"example-app-core": {}}})
            failures = vs.check_impl_repos(schemas, path, root / "guards")
            self.assertEqual(failures, [])


class TestTerminalStatuses(unittest.TestCase):
    def test_only_empty_transition_lists_are_terminal(self):
        self.assertEqual(vs.terminal_statuses(SAMPLE_TRANSITIONS), {"merged", "abandoned"})

    def test_spec_clarify_pending_not_terminal_despite_wip_exclusion(self):
        # It has real outgoing edges (self-loop, spec-pending, abandoned) --
        # it's PARKED, not terminal. See check_queue's not_active derivation.
        self.assertNotIn("spec-clarify-pending", vs.terminal_statuses(SAMPLE_TRANSITIONS))

    def test_empty_table_is_no_terminal_statuses(self):
        self.assertEqual(vs.terminal_statuses({}), set())


class TestCheckTransitionsSync(unittest.TestCase):
    def _schemas(self, tmp, schema=QUEUE_CLAIM_SCHEMA_WITH_ENUM):
        root = make_root(tmp, schemas={"queue-claim": schema})
        schemas, _ = vs.load_schemas(root / "schemas")
        return schemas

    def test_matching_sets_no_failures(self):
        with tempfile.TemporaryDirectory() as d:
            schemas = self._schemas(Path(d))
            failures = vs.check_transitions_sync(
                schemas, SAMPLE_TRANSITIONS, Path("state/transitions.json"), Path("schemas/queue-claim.schema.json"),
            )
            self.assertEqual(failures, [])

    def test_enum_value_missing_from_table_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            schemas = self._schemas(Path(d))
            table = {k: v for k, v in SAMPLE_TRANSITIONS.items() if k != "abandoned"}
            failures = vs.check_transitions_sync(
                schemas, table, Path("state/transitions.json"), Path("schemas/queue-claim.schema.json"),
            )
            self.assertTrue(any("'abandoned' is a valid queue-claim status but has no transitions entry" in f
                                for f in failures))

    def test_table_key_missing_from_enum_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            schemas = self._schemas(Path(d))
            table = dict(SAMPLE_TRANSITIONS, **{"pr-open": []})
            failures = vs.check_transitions_sync(
                schemas, table, Path("state/transitions.json"), Path("schemas/queue-claim.schema.json"),
            )
            self.assertTrue(any("'pr-open' is in transitions.json but not the status enum" in f for f in failures))

    def test_no_schema_no_crash(self):
        failures = vs.check_transitions_sync(
            {}, SAMPLE_TRANSITIONS, Path("state/transitions.json"), Path("schemas/queue-claim.schema.json"),
        )
        self.assertEqual(failures, [])

    def test_empty_transitions_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            schemas = self._schemas(Path(d))
            failures = vs.check_transitions_sync(
                schemas, {}, Path("state/transitions.json"), Path("schemas/queue-claim.schema.json"),
            )
            self.assertEqual(failures, [])


TRIVIAL_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}


def make_clean_state(root: Path) -> None:
    """All six live-state files present and minimally valid, matching how
    they always exist in the real repo (schema-validate.yml's 'clean' case)."""
    make_root(root, schemas={
        "queue-claim": QUEUE_CLAIM_SCHEMA_WITH_ENUM,
        "dependabot-repos": TRIVIAL_SCHEMA,
        "impl-repos": TRIVIAL_SCHEMA,
        "autonomy-ledger": TRIVIAL_SCHEMA,
        "provenance": TRIVIAL_SCHEMA,
    })
    (root / "schemas" / "fixtures").mkdir(parents=True)
    (root / "guards").mkdir()
    write(root / "state" / "queue.json", {"wip_cap": 2, "claims": []})
    write(root / "state" / "transitions.json", SAMPLE_TRANSITIONS)
    write(root / "state" / "dependabot-repos.json", {"reviewers": {"pool": ["alice"], "out": []}})
    write(root / "state" / "impl-repos.json", {"repos": {}})
    write(root / "state" / "autonomy-ledger.json", {})
    write(root / "state" / "provenance.json", {})


class TestRun(unittest.TestCase):
    def test_clean_repo_reports_zero_failures(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_clean_state(root)
            failures, schema_count = vs.run(root)
            self.assertEqual(failures, [])
            self.assertEqual(schema_count, 5)

    def test_aggregates_failures_across_all_checks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_root(root, schemas={"impl-repos": IMPL_REPOS_SCHEMA})
            (root / "schemas" / "fixtures").mkdir(parents=True)
            (root / "guards").mkdir()
            write(root / "state" / "impl-repos.json", {"repos": {"orphaned-repo": {}}})
            write(root / "state" / "queue.json", {"wip_cap": "bad", "claims": []})
            failures, schema_count = vs.run(root)
            self.assertTrue(any("orphaned-repo" in f for f in failures))
            self.assertTrue(any("must have integer wip_cap" in f for f in failures))
            self.assertEqual(schema_count, 1)


class TestMain(unittest.TestCase):
    def test_exit_1_on_failures(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_clean_state(root)
            write(root / "state" / "queue.json", {"wip_cap": "bad", "claims": []})
            self.assertEqual(vs.main(["validate-state.py", str(root)]), 1)

    def test_exit_0_on_clean(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_clean_state(root)
            self.assertEqual(vs.main(["validate-state.py", str(root)]), 0)


if __name__ == "__main__":
    unittest.main()
