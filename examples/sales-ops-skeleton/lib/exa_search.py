#!/usr/bin/env python3
"""CLI wrapper for Exa neural search. Used by enrichment + stack-profile agents.

Usage:
  python3 lib/exa_search.py "<query>" [--num-results N] [--type auto|fast|deep] [--include-domains d1 d2] [--max-age-hours H]

Outputs a JSON array to stdout: [{title, url, published_date, highlights}]
Exits 1 and prints {"error": "..."} on failure.
"""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Exa neural search CLI")
    parser.add_argument("query")
    parser.add_argument("--type", default="auto",
                        choices=["auto", "fast", "instant", "deep-lite", "deep", "deep-reasoning"])
    parser.add_argument("--num-results", type=int, default=5)
    parser.add_argument("--include-domains", nargs="+")
    parser.add_argument("--max-age-hours", type=int)
    args = parser.parse_args()

    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        print(json.dumps({"error": "EXA_API_KEY not set"}))
        sys.exit(1)

    try:
        from exa_py import Exa
    except ImportError:
        print(json.dumps({"error": "exa-py not installed; run: pip install exa-py==2.14.0"}))
        sys.exit(1)

    exa = Exa(api_key=api_key)

    contents = {"highlights": True}
    if args.max_age_hours is not None:
        contents["max_age_hours"] = args.max_age_hours

    kwargs = {
        "type": args.type,
        "num_results": args.num_results,
        "contents": contents,
    }
    if args.include_domains:
        kwargs["include_domains"] = args.include_domains

    try:
        results = exa.search(args.query, **kwargs)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    output = []
    for r in results.results:
        output.append({
            "title": r.title,
            "url": r.url,
            "published_date": getattr(r, "published_date", None),
            "highlights": getattr(r, "highlights", []),
        })

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
