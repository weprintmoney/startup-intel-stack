#!/usr/bin/env python3
"""
Fail a workflow before scoring when the doc a scoring agent was calibrated
against has moved since its CLAUDE.md was last reviewed.

Each scoring agent's CLAUDE.md declares one or more lines:

    Calibrated-against: <path-relative-to-docs-root> <key>=<value>

This confirms `<key>` still holds `<value>` in the checked-out copy of that
doc — as `key: value`, `key: "value"`, or `"key": "value"`, so it matches
plain YAML config and JSON-shaped rubric output-schema blocks alike. A doc
that moved without a matching CLAUDE.md update is silent skew; a loud
pre-flight failure here is cheaper than a lead scored against a stale
rubric.

Usage:
    python scripts/check_doc_version.py <claude_md_path> [--docs-root docs]
"""

import argparse
import re
import sys
from pathlib import Path

DECLARATION_RE = re.compile(r"^Calibrated-against:\s+(\S+)\s+(\w+)=(\S+)\s*$")
VALUE_TEMPLATE = r'["\']?\b{key}\b["\']?\s*[:=]\s*["\']?([^"\',\s]+)["\']?'


def declarations(claude_md_path: Path) -> list[tuple[str, str, str]]:
    """Parse `Calibrated-against:` lines from a CLAUDE.md into (doc, key, value)."""
    out = []
    for line in claude_md_path.read_text().splitlines():
        m = DECLARATION_RE.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2), m.group(3)))
    return out


def check_one(docs_root: Path, doc: str, key: str, expected: str) -> str | None:
    """Return an error message, or None if `key` holds `expected` in `doc`."""
    doc_path = docs_root / doc
    if not doc_path.is_file():
        return f"declared doc not found: {doc} (looked in {doc_path})"

    text = doc_path.read_text()
    value_re = re.compile(VALUE_TEMPLATE.format(key=re.escape(key)))
    found = {m.group(1) for m in value_re.finditer(text)}

    if not found:
        return f"{key} not found anywhere in {doc}"
    if len(found) > 1:
        return f"{key} has multiple conflicting values in {doc}: {sorted(found)}"
    (actual,) = found
    if actual != expected:
        return f"{key} mismatch in {doc}: CLAUDE.md declares {expected!r}, doc has {actual!r}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claude_md", help="Path to the scoring agent's CLAUDE.md")
    parser.add_argument(
        "--docs-root", default="docs",
        help="Root of the docs SSOT tree (default: docs -- same repo here, no separate checkout)",
    )
    args = parser.parse_args()

    claude_md_path = Path(args.claude_md)
    decls = declarations(claude_md_path)
    if not decls:
        print(f"::error::no Calibrated-against declarations found in {claude_md_path}")
        return 1

    docs_root = Path(args.docs_root)
    errors = []
    for doc, key, expected in decls:
        err = check_one(docs_root, doc, key, expected)
        if err:
            errors.append(err)
        else:
            print(f"OK: {doc} {key}={expected}")

    for e in errors:
        print(f"::error::{e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
