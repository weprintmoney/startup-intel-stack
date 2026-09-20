"""CRM prior-contact dedup gate.

Extracted from dedup.yml's inline heredoc. Behavior-preserving: same
already-deduped skip, same malformed-file skip, same name-based CRM
lookup, same summary line format.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crm  # noqa: E402


def dedup_leads(leads: list[dict]) -> tuple[list[dict], int]:
    survivors = []
    skipped = 0
    for lead in leads:
        name = lead.get("contact_name", "")
        company = lead.get("company_name", "")
        if not name:
            lead["prior_contact"] = False
            survivors.append(lead)
            continue
        matches = crm.search_by_name(name)
        if matches:
            skipped += 1
            print(f"Skipping {name} at {company}: already in CRM ({len(matches)} record(s))")
        else:
            lead["prior_contact"] = False
            survivors.append(lead)
    return survivors, skipped


def dedup_file(raw_path: Path, deduped_dir: Path) -> None:
    suffix = raw_path.name
    out_path = deduped_dir / suffix
    if out_path.exists():
        print(f"Already deduped: {suffix}")
        return

    try:
        leads = json.loads(raw_path.read_text())
    except Exception as e:
        print(f"Skipping {raw_path}: {e}")
        return
    if not isinstance(leads, list):
        leads = [leads]

    survivors, skipped = dedup_leads(leads)

    out_path.write_text(json.dumps(survivors, indent=2))
    print(f"\nDedup summary {suffix}")
    print(f"  Input:   {len(leads)} leads")
    print(f"  Skipped: {skipped} (already in CRM)")
    print(f"  Output:  {len(survivors)} leads -> {out_path}")


def run(raw_dir: Path, deduped_dir: Path) -> None:
    deduped_dir.mkdir(parents=True, exist_ok=True)
    for raw_path in sorted(raw_dir.glob("*.json")):
        dedup_file(raw_path, deduped_dir)


def main() -> int:
    run(Path("leads/raw"), Path("leads/deduped"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
