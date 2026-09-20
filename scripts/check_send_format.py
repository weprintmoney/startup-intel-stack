#!/usr/bin/env python3
"""
Fail a PR whose queued copy carries hard-wrapped line breaks.

What sits in `sends/` is what goes out — smtp-send passes `body` to Resend
verbatim — so the queue file has to hold the finished shape: one line per
paragraph, blank line between paragraphs, no mid-sentence newlines.

Usage:
    python scripts/check_send_format.py          # report and exit 1 on offenders
    python scripts/check_send_format.py --fix    # rewrite them in place
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from format_body import unwrap_body  # noqa: E402

SEND_DIRS = ["sends/queue", "sends/format-test-queue", "sends/linkedin"]


def main() -> int:
    fix = "--fix" in sys.argv
    offenders = []

    for directory in SEND_DIRS:
        for path in sorted(Path(directory).glob("*.json")):
            item = json.loads(path.read_text())
            body = item.get("body")
            if not isinstance(body, str):
                continue

            unwrapped = unwrap_body(body)
            if unwrapped == body:
                continue

            offenders.append(path)
            if fix:
                item["body"] = unwrapped
                path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n")

    if not offenders:
        print("All queued bodies are unwrapped.")
        return 0

    verb = "Unwrapped" if fix else "Hard-wrapped body in"
    for path in offenders:
        print(f"{verb} {path}")
    if fix:
        return 0

    print(
        f"\n{len(offenders)} file(s) carry hard line breaks mid-paragraph. "
        "Run: python scripts/check_send_format.py --fix"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
