#!/usr/bin/env python3
"""State/schema validation (including claim transitions).

Extracted from schema-validate.yml's "Validate schemas, fixtures, and
state" inline heredoc. Behavior-preserving: same schema/fixture checks,
same live-state invariants (queue wip_cap vs. active claims, dependabot
reviewer pool, impl-repos/guards symmetric difference), same failure
list and exit-code shape.

state/transitions.json is the single source of truth for
queue-claim's status enum (enforced at write time by
scripts/update-claim.sh). This module cross-checks the schema's enum
against transitions.json's keys instead of trusting them to stay in
sync by hand, and derives the queue's "not consuming a WIP slot" set
from transitions.json's terminal states (empty transition list) plus
the one documented non-terminal exception (spec-clarify-pending is
parked, not done -- see queue-claim.schema.json's status description),
replacing the old hardcoded three-value tuple.

Run directly: `python3 scripts/validate-state.py [repo-root]` (defaults
to the current directory). Exit 0 = clean, 1 = failures printed to stdout.
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

# Parked, not terminal: holds no WIP slot but has real outgoing transitions
# (a human answers the clarifying question and spec-draft re-dispatches).
PARKED_STATUSES = {"spec-clarify-pending"}


def load(p: Path) -> tuple[object | None, str | None]:
    try:
        return json.loads(p.read_text()), None
    except Exception as e:
        return None, f"{p}: unparseable JSON — {e}"


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


def validate_instance(schemas: dict, name: str, instance: object, path: Path) -> list[str]:
    v = schemas.get(name)
    if v is None:
        return [f"{path}: no schema named {name}"]
    errs = sorted(v.iter_errors(instance), key=lambda e: e.json_path)
    return [f"{path}: {e.json_path}: {e.message}" for e in errs]


def check_fixtures(schemas: dict, fixtures_dir: Path) -> list[str]:
    failures = []
    for fx in sorted(fixtures_dir.glob("*.example.json")):
        inst, err = load(fx)
        if err:
            failures.append(err)
            continue
        failures += validate_instance(schemas, fx.name.replace(".example.json", ""), inst, fx)
    return failures


def terminal_statuses(transitions: dict) -> set[str]:
    """Statuses with no outgoing transitions (true dead ends)."""
    return {s for s, edges in transitions.items() if not edges}


def check_transitions_sync(schemas: dict, transitions: dict, transitions_path: Path, schema_path: Path) -> list[str]:
    """The queue-claim schema's status enum and transitions.json's keys must
    name the same set of statuses. Drift either way is dangerous: a status
    the schema allows but the table doesn't know about is treated by
    update-claim.sh as having zero legal destinations (accidentally
    terminal); a status the table knows about but the schema doesn't allow
    would fail schema validation the moment update-claim.sh wrote it."""
    v = schemas.get("queue-claim")
    if v is None or not transitions:
        return []
    enum = set(v.schema.get("properties", {}).get("status", {}).get("enum", []))
    table = set(transitions.keys())
    failures = []
    for s in sorted(enum - table):
        failures.append(f"{transitions_path}: '{s}' is a valid queue-claim status but has no transitions entry")
    for s in sorted(table - enum):
        failures.append(f"{schema_path}: '{s}' is in transitions.json but not the status enum")
    return failures


def check_queue(schemas: dict, path: Path, transitions: dict) -> list[str]:
    q, err = load(path)
    if err:
        return [err]
    if q is None:
        return []
    if not isinstance(q.get("wip_cap"), int) or not isinstance(q.get("claims"), list):
        return [f"{path}: must have integer wip_cap and array claims"]
    failures = []
    not_active = terminal_statuses(transitions) | PARKED_STATUSES
    active = [c for c in q["claims"] if c.get("status") not in not_active]
    if len(active) > q["wip_cap"]:
        failures.append(f"{path}: active claims exceed wip_cap")
    # One row per (issue, impl_repo). update-claim.sh reads the claim's status
    # by key; two rows for one key (a stale terminal row beside a re-claim)
    # made every transition fail as illegal.
    rows: dict[tuple, int] = {}
    for c in q["claims"]:
        if "issue" in c and "impl_repo" in c:
            key = (c["issue"], c["impl_repo"])
            rows[key] = rows.get(key, 0) + 1
    for (issue, impl_repo), n in sorted(rows.items(), key=lambda kv: str(kv[0])):
        if n > 1:
            failures.append(
                f"{path}: {n} rows for claim #{issue} in {impl_repo} — one row per (issue, impl_repo); "
                "drop the terminal row (ticket-intake replaces it on re-claim)"
            )
    for i, claim in enumerate(q["claims"]):
        failures += validate_instance(schemas, "queue-claim", claim, f"{path} claims[{i}]")
    return failures


def check_dependabot_repos(schemas: dict, path: Path) -> list[str]:
    dep, err = load(path)
    if err:
        return [err]
    if dep is None:
        return []
    failures = validate_instance(schemas, "dependabot-repos", dep, path)
    rv = dep.get("reviewers") or {}
    pool = rv.get("pool") or []
    out = rv.get("out") or []
    for o in out:
        if o not in pool:
            failures.append(f"{path}: reviewers.out '{o}' is not in reviewers.pool")
    if not [p for p in pool if p not in out]:
        failures.append(f"{path}: reviewers.pool has no active member (everyone is out)")
    return failures


def check_impl_repos(schemas: dict, path: Path, guards_dir: Path) -> list[str]:
    reg, err = load(path)
    if err:
        return [err]
    if reg is None:
        return []
    failures = validate_instance(schemas, "impl-repos", reg, path)
    registered = set((reg.get("repos") or {}).keys())
    guarded = {p.stem for p in guards_dir.glob("*.paths")}
    for r in sorted(registered - guarded):
        failures.append(
            f"{path}: '{r}' is registered but has no {guards_dir.name}/{r}.paths — "
            "add the expertise-path list (empty is valid) before the pipeline touches it"
        )
    for g in sorted(guarded - registered):
        failures.append(
            f"{guards_dir.name}/{g}.paths: no entry in {path} — register the repo "
            "(routable: false is fine) so the ledger and reapers know it"
        )
    return failures


def check_ledger_and_provenance(schemas: dict, state_dir: Path) -> list[str]:
    failures = []
    for name, schema_name in (("autonomy-ledger.json", "autonomy-ledger"), ("provenance.json", "provenance")):
        path = state_dir / name
        inst, err = load(path)
        if err:
            failures.append(err)
        elif inst is not None:
            failures += validate_instance(schemas, schema_name, inst, path)
    return failures


def check_releases(schemas: dict, state_dir: Path) -> list[str]:
    failures = []
    for ff in sorted(state_dir.glob("releases/*/findings.json")):
        inst, err = load(ff)
        if err:
            failures.append(err)
        elif inst is not None:
            failures += validate_instance(schemas, "release-findings", inst, ff)
    for pf in sorted(state_dir.glob("releases/*/proposed-tickets.json")):
        _, err = load(pf)
        if err:
            failures.append(err)
    for cv in sorted(state_dir.glob("releases/*/claim-verdict.json")):
        inst, err = load(cv)
        if err:
            failures.append(err)
        elif inst is not None:
            failures += validate_instance(schemas, "claim-verdict", inst, cv)
    return failures


def run(root: Path) -> tuple[list[str], int]:
    schemas, failures = load_schemas(root / "schemas")
    failures = list(failures)
    failures += check_fixtures(schemas, root / "schemas" / "fixtures")

    transitions_path = root / "state" / "transitions.json"
    transitions, err = load(transitions_path)
    if err:
        failures.append(err)
    if not isinstance(transitions, dict):
        transitions = {}

    schema_path = root / "schemas" / "queue-claim.schema.json"
    failures += check_transitions_sync(schemas, transitions, transitions_path, schema_path)
    failures += check_queue(schemas, root / "state" / "queue.json", transitions)
    failures += check_dependabot_repos(schemas, root / "state" / "dependabot-repos.json")
    failures += check_impl_repos(schemas, root / "state" / "impl-repos.json", root / "guards")
    failures += check_ledger_and_provenance(schemas, root / "state")
    failures += check_releases(schemas, root / "state")
    return failures, len(schemas)


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(".")
    failures, schema_count = run(root)
    if failures:
        print("SCHEMA VALIDATION FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"All schemas, fixtures, and state files valid ({schema_count} schemas).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
