#!/usr/bin/env python3
"""Node-docs drift check (P4 ops-maintainability, step A4).

Two assertions, both against a repo root:
  a. every `.github/workflows/*.yml` filename appears somewhere in `README.md`
  b. every `agents/*/CLAUDE.md` has a sibling `README.md` whose top-level
     (`##`) headings contain the 10-section order from CLAUDE.md's
     `## Patterns`, in order (extra headings are fine; missing or
     out-of-order ones are not)

Fence-aware: a `## `-looking line inside a fenced code block (```` ``` ````)
is not a real heading and is ignored (agents/code-judge/CLAUDE.md:55 has one
in an example output block — the same care applies to any README that
quotes example output).

Run directly: `python3 scripts/check-node-docs.py [repo-root]` (defaults to
the current directory). Exit 0 = clean, 1 = failures printed to stdout.
"""
import re
import sys
from pathlib import Path

EXPECTED_HEADINGS = [
    "Purpose",
    "Trigger and cadence",
    "Inputs",
    "Outputs",
    "Secrets and variables",
    "Run it by hand",
    "Pause / kill switch",
    "How it fails and where the alert goes",
    "Files this node touches",
    "Owner",
]

HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def strip_fences(text: str) -> str:
    """Drop the contents of ``` ... ``` blocks so example headings inside them don't count."""
    out_lines = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out_lines.append(line)
    return "\n".join(out_lines)


def h2_headings(text: str) -> list[str]:
    return [m.group(1).strip() for m in HEADING_RE.finditer(strip_fences(text))]


def check_workflow_readme_parity(root: Path, readme_name: str = "README.md") -> list[str]:
    failures = []
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.exists():
        return failures
    readme_path = root / readme_name
    readme_text = readme_path.read_text() if readme_path.exists() else ""
    if not readme_path.exists():
        failures.append(f"MISSING {readme_name} at repo root")
        return failures
    for wf in sorted(workflows_dir.glob("*.yml")):
        if wf.name not in readme_text:
            failures.append(f"workflow {wf.name} not mentioned in {readme_name}")
    return failures


def check_node_readmes(root: Path) -> list[str]:
    failures = []
    agents_dir = root / "agents"
    if not agents_dir.exists():
        return failures
    for claude_md in sorted(agents_dir.glob("*/CLAUDE.md")):
        node = claude_md.parent.name
        readme_path = claude_md.parent / "README.md"
        if not readme_path.exists():
            failures.append(f"agents/{node}/README.md missing (sibling of CLAUDE.md)")
            continue
        headings = h2_headings(readme_path.read_text())
        idx = 0
        for h in headings:
            if idx < len(EXPECTED_HEADINGS) and h == EXPECTED_HEADINGS[idx]:
                idx += 1
        if idx != len(EXPECTED_HEADINGS):
            failures.append(
                f"agents/{node}/README.md: expected heading {EXPECTED_HEADINGS[idx]!r} "
                f"next (in order), found headings {headings}"
            )
    return failures


def check(root: Path) -> list[str]:
    return check_workflow_readme_parity(root) + check_node_readmes(root)


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(".")
    failures = check(root)
    if failures:
        print(f"check-node-docs: {len(failures)} failure(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("check-node-docs: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
