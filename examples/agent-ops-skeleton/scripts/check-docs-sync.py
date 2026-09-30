#!/usr/bin/env python3
"""Docs-sync check: does the developer guide still match the pipeline it describes.

Built for a recurring failure mode: a PR changes `state/transitions.json`
or adds a workflow, and the developer guide (by default
`internal-docs/07-engineering-docs/development/agent-ops/reference.md`;
override with the `DEV_GUIDE_PATH` repo variable) needs a manual,
easy-to-forget follow-up pass to stay accurate. The existing dream-loop `doc-drift-miner` doesn't cover this:
it watches product-repo changes against knowledge-graph nodes, never
agent-ops's own changes against these plain (non-graph) procedural pages.

Two purely mechanical checks, both cheap enough to need no model call
("anything a grep can decide lives here with a unit test, not in the
prompt" -- verify-claims.py's own principle):

  1. transitions   -- every edge in state/transitions.json appears in
                       reference.md's "## Claim states" table, and vice
                       versa (an edge documented that no longer exists).
  2. workflow-files -- every `.github/workflows/*.yml` file is mentioned
                       somewhere in reference.md, and vice versa (a
                       workflow documented that was renamed or removed).

Advisory only -- always exits 0. Docs live in a different repo; this
pipeline has no business blocking its own merges over another repo's
page. The workflow that calls this posts findings to Slack for a human to
act on.

Known limitation, accepted for v1: the transitions-table parser is a
tolerant regex over a markdown cell, not a real markdown parser. A stray
backtick-quoted word inside a table cell's explanatory prose (there is
none today) could produce a false positive. Advisory severity makes that
an acceptable trade for staying dependency-free and simple; if it becomes
a recurring nuisance, move the machine-readable copy into a fenced code
block the way round-history.py embeds its JSON, and parse that instead of
the prose.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TRANSITIONS_HEADER = "## Claim states"
STATE_RE = re.compile(r"`([a-z][a-z-]*)`")

# reference.md's Workflows table is a lifecycle cheat sheet for someone
# queuing and reviewing tickets -- deliberately not an exhaustive inventory.
# Excluded on purpose: pure CI/lint/tooling infra (a dev never dispatches
# these), reusable guard workflows called BY other repos rather than run
# here, and the eval/regression suites (covered instead, in the right
# context, by your developer guide's symptom table). Add here rather than
# widening reference.md's scope when a new one of these lands.
EXCLUDED_WORKFLOWS = {
    "lint.yml",
    "schema-validate.yml",
    "install-preflight.yml",
    "expertise-path-guard.yml",
    "footprint-scan.yml",
    "docs-sync-check.yml",
    "judge-evals.yml",
    "judge-evals-repeat.yml",
    "failure-mode-evals.yml",
    "verifier-evals.yml",
    "claim-verify-evals.yml",
}


def load_transitions(path: Path) -> dict[str, set[str]]:
    data = json.loads(path.read_text())
    return {state: set(edges) for state, edges in data.items()}


def extract_docs_transitions(reference_md: str) -> dict[str, set[str]]:
    """Parse the markdown table under "## Claim states" into {from: {to, ...}}.

    Table rows look like:
        | `spec-approved` | `implementing`, `abandoned` (added ...) |
        | `merged`, `abandoned` | terminal |
    Every backtick-quoted token in the first cell is a from-state (a row can
    document more than one terminal state at once); each maps to every
    backtick-quoted token in the rest of that row (empty for "terminal",
    correctly matching transitions.json's `[]`). Rows outside a
    `| ... | ... |` shape, or before the header, are ignored.
    """
    if TRANSITIONS_HEADER not in reference_md:
        return {}
    section = reference_md.split(TRANSITIONS_HEADER, 1)[1]
    # Stop at the next H2 so a later section's tables are never mistaken
    # for this one.
    section = section.split("\n## ", 1)[0]
    out: dict[str, set[str]] = {}
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        from_states = STATE_RE.findall(cells[0])
        if not from_states:
            continue
        to_states = set(STATE_RE.findall(cells[1]))
        for from_state in from_states:
            out[from_state] = to_states
    return out


def diff_transitions(live: dict[str, set[str]], docs: dict[str, set[str]]) -> list[str]:
    findings = []
    for state, edges in live.items():
        doc_edges = docs.get(state)
        if doc_edges is None:
            findings.append(
                f"transitions: `{state}` is in transitions.json but has no row in reference.md's Claim states table"
            )
            continue
        missing = edges - doc_edges
        if missing:
            findings.append(
                f"transitions: `{state}` -> {sorted(missing)} exists in transitions.json "
                "but reference.md's table doesn't list it"
            )
    for state, doc_edges in docs.items():
        live_edges = live.get(state)
        if live_edges is None:
            findings.append(
                f"transitions: reference.md documents `{state}` as a state, but it's not a key in transitions.json"
            )
            continue
        extra = doc_edges - live_edges
        if extra:
            findings.append(
                f"transitions: reference.md says `{state}` -> {sorted(extra)}, "
                "but transitions.json no longer allows that"
            )
    return findings


def diff_workflow_files(workflows_dir: Path, reference_md: str) -> list[str]:
    live_files = {p.name for p in workflows_dir.glob("*.yml")} - EXCLUDED_WORKFLOWS
    documented = set(re.findall(r"`([a-z][a-z0-9_-]*\.yml)`", reference_md)) - EXCLUDED_WORKFLOWS
    findings = []
    for name in sorted(live_files - documented):
        findings.append(f"workflow-files: `{name}` exists in .github/workflows/ but reference.md never mentions it")
    for name in sorted(documented - live_files):
        findings.append(f"workflow-files: reference.md mentions `{name}`, which no longer exists in .github/workflows/")
    return findings


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check-docs-sync.py <path-to-reference.md>", file=sys.stderr)
        return 2
    reference_md = Path(sys.argv[1]).read_text()
    root = Path(__file__).resolve().parent.parent

    live_transitions = load_transitions(root / "state" / "transitions.json")
    docs_transitions = extract_docs_transitions(reference_md)

    findings = []
    findings += diff_transitions(live_transitions, docs_transitions)
    findings += diff_workflow_files(root / ".github" / "workflows", reference_md)

    if findings:
        print(f"check-docs-sync: {len(findings)} finding(s) — advisory, never blocks the build")
        for f in findings:
            print(f"  - {f}")
    else:
        print("check-docs-sync: reference.md matches transitions.json and the workflow file list")
    return 0  # advisory: always exits 0, see module docstring


if __name__ == "__main__":
    sys.exit(main())
