"""Data schema validation for this repo's lead/send/suppression files.

Several workflows commit data straight to main as a bot account, so a PR check
never sees most of these writes. Two scopes, one validator:

  - "pr" scope: sends/queue/** and sends/linkedin/** only -- the only data
    paths a human ever sees in a PR (sequence-enrollment's approval PR is
    the human-approval gate, Hard Rule 1). Used by data-validate.yml's
    pull_request trigger to GATE the merge.
  - "full" scope: every schema-covered directory. Used by data-validate.yml's
    push trigger, which is ADVISORY (never fails the run) -- it posts a
    Slack alert on failure instead of blocking anything, since there is no
    PR left to block by the time a bot push lands on main.

Both scopes also validate every schemas/*.schema.json file is itself a
valid JSON Schema, since a human edits those directly.
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ARRAY_DIRS = {
    "leads/raw": "lead-raw",
    "leads/deduped": "lead-deduped",
    "leads/critic": "critic-verdict",
    "leads/stack-profiles": "stack-profile",
    "leads/org-profiles": "org-context-profile",
    "leads/companies": "company-lead",
    "sends/verdicts": "copy-verdict",
}

SINGLE_FILE_DIRS = {
    "sends/queue": "send-touch",
    "sends/linkedin": "send-touch",
    "sends/rejected": "send-touch",
    "sends/format-test-queue": "send-touch-format-test",
}


def load(p: Path) -> tuple[object | None, str | None]:
    try:
        return json.loads(p.read_text()), None
    except Exception as e:
        return None, f"{p}: unparseable JSON — {e}"


def load_jsonl(p: Path) -> tuple[list | None, str | None]:
    try:
        records = []
        for line in p.read_text().splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
        return records, None
    except Exception as e:
        return None, f"{p}: unparseable JSONL — {e}"


def load_schemas(schemas_dir: Path) -> tuple[dict, list[str]]:
    schemas = {}
    failures = []
    for sf in sorted(schemas_dir.glob("*.schema.json")):
        inst, err = load(sf)
        if err:
            failures.append(err)
            continue
        try:
            Draft202012Validator.check_schema(inst)
        except Exception as e:
            failures.append(f"{sf}: invalid schema — {e}")
            continue
        schemas[sf.stem.replace(".schema", "")] = Draft202012Validator(inst, format_checker=FormatChecker())
    return schemas, failures


def validate_instance(schemas: dict, name: str, instance: object, path) -> list[str]:
    v = schemas.get(name)
    if v is None:
        return [f"{path}: no schema named {name}"]
    errs = sorted(v.iter_errors(instance), key=lambda e: e.json_path)
    return [f"{path}: {e.json_path}: {e.message}" for e in errs]


def check_array_file(schemas: dict, name: str, path: Path) -> list[str]:
    """path holds a JSON array; validate every element against `name`."""
    d, err = load(path)
    if err:
        return [err]
    if not isinstance(d, list):
        return [f"{path}: expected a JSON array"]
    failures = []
    for i, rec in enumerate(d):
        failures += validate_instance(schemas, name, rec, f"{path}[{i}]")
    return failures


def check_single_file(schemas: dict, name: str, path: Path) -> list[str]:
    d, err = load(path)
    if err:
        return [err]
    return validate_instance(schemas, name, d, path)


def check_jsonl_file(schemas: dict, name: str, path: Path) -> list[str]:
    records, err = load_jsonl(path)
    if err:
        return [err]
    failures = []
    for i, rec in enumerate(records):
        failures += validate_instance(schemas, name, rec, f"{path}:{i + 1}")
    return failures


def schema_for_prefiltered(path: Path) -> str:
    return "lead-reject" if path.name.endswith("-rejects.json") else "lead-pre-filtered"


def check_pr_scope(schemas: dict, root: Path) -> list[str]:
    """sends/queue/** and sends/linkedin/** -- the only data a human PR ever touches."""
    failures = []
    for rel in ("sends/queue", "sends/linkedin"):
        for fp in sorted((root / rel).glob("*.json")):
            failures += check_single_file(schemas, "send-touch", fp)
    return failures


def check_full_scope(schemas: dict, root: Path) -> list[str]:
    """Every schema-covered directory -- push-advisory scope."""
    failures = []
    for rel, name in ARRAY_DIRS.items():
        for fp in sorted((root / rel).glob("*.json")):
            failures += check_array_file(schemas, name, fp)

    for fp in sorted((root / "leads" / "pre-filtered").glob("*.json")):
        failures += check_array_file(schemas, schema_for_prefiltered(fp), fp)

    for fp in sorted((root / "leads" / "enriched").glob("*.json")):
        failures += check_array_file(schemas, "lead-enriched", fp)

    for rel, name in SINGLE_FILE_DIRS.items():
        for fp in sorted((root / rel).glob("*.json")):
            failures += check_single_file(schemas, name, fp)

    suppression_path = root / "suppression" / "list.jsonl"
    if suppression_path.exists():
        failures += check_jsonl_file(schemas, "suppression-line", suppression_path)

    daily_count_path = root / "sends" / "daily-count.json"
    if daily_count_path.exists():
        failures += check_single_file(schemas, "daily-count", daily_count_path)

    # Manual-send outcomes: appended by lead-issue-sync.yml and by hand.
    outcomes_path = root / "sends" / "outcomes.jsonl"
    if outcomes_path.exists():
        failures += check_jsonl_file(schemas, "outcome-line", outcomes_path)

    return failures


def run(root: Path, scope: str) -> tuple[list[str], int]:
    schemas, failures = load_schemas(root / "schemas")
    failures = list(failures)
    failures += (check_pr_scope if scope == "pr" else check_full_scope)(schemas, root)
    return failures, len(schemas)


def main(argv: list[str]) -> int:
    scope = argv[1] if len(argv) > 1 else "full"
    root = Path(argv[2]) if len(argv) > 2 else Path(".")
    if scope not in ("pr", "full"):
        print(f"usage: validate_data.py [pr|full] [repo-root] (got scope={scope!r})")
        return 2
    failures, schema_count = run(root, scope)
    if failures:
        print(f"DATA VALIDATION FAILED ({scope} scope):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"All data files valid ({scope} scope, {schema_count} schemas).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
