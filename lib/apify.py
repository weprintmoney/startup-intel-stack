#!/usr/bin/env python3
"""Thin synchronous Apify client + CLI. Used by the apify-ingest agent.

Standard library only (urllib) — CI installs nothing beyond jsonschema and
pyyaml for lib/. Every call needs APIFY_API_KEY in the environment (the older
name APIFY_TOKEN is accepted as a fallback); the apify-ingest workflow's
preflight gate never lets this run without it, and the CLI exits 1 with a JSON
error if it is missing.

Usage:
  python3 lib/apify.py run --actor <user/name> --input-file in.json \
      [--max-items N] [--out out.json] [--timeout-s 1800] [--dry-run]

Outputs the dataset items as a JSON array (to --out, or stdout). Exits 1 and
prints {"error": "..."} on any failure. --dry-run prints the request that would
be made and exits 0 without touching the network.

API surface (https://docs.apify.com/api/v2):
  POST /v2/acts/{user~name}/runs?timeout=..&memory=..   -> {data: {id, defaultDatasetId, status}}
  GET  /v2/actor-runs/{run_id}                           -> {data: {status, defaultDatasetId}}
  GET  /v2/datasets/{dataset_id}/items?format=json&clean=true&limit=..&offset=..
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.apify.com/v2"
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}
DEFAULT_TIMEOUT_S = 1800
DEFAULT_POLL_S = 15
PAGE_SIZE = 500
REQUEST_TIMEOUT_S = 30

# Actor inputs that would carry a logged-in LinkedIn session. Refused outright:
# public-page actors only, so no staff account is ever exposed.
FORBIDDEN_INPUT_KEYS = ("cookie", "cookies", "li_at", "sessioncookie", "session_cookie")


class ApifyError(RuntimeError):
    pass


def actor_path(actor: str) -> str:
    """'user/name' -> 'user~name' (the path form the acts endpoint expects)."""
    actor = actor.strip()
    if "~" in actor:
        return actor
    if "/" not in actor:
        raise ApifyError(f"actor must be 'user/name' or 'user~name', got {actor!r}")
    user, name = actor.split("/", 1)
    return f"{user}~{name}"


def forbidden_input_keys(run_input: dict) -> list[str]:
    """Return any input keys that look like session credentials (case-insensitive, nested)."""
    found = []

    def walk(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{prefix}{k}"
                if str(k).lower().replace("-", "_") in FORBIDDEN_INPUT_KEYS:
                    found.append(key)
                walk(v, key + ".")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{prefix}{i}.")

    walk(run_input)
    return found


TOKEN_ENV_VARS = ("APIFY_API_KEY", "APIFY_TOKEN")


def _token() -> str:
    for name in TOKEN_ENV_VARS:
        tok = os.environ.get(name, "").strip()
        if tok:
            return tok
    raise ApifyError("APIFY_API_KEY not set")


def token_present() -> bool:
    return any(os.environ.get(n, "").strip() for n in TOKEN_ENV_VARS)


def _request(method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> dict | list:
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
            "User-Agent": "startup-intel-stack/apify-ingest",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise ApifyError(f"HTTP {e.code} on {method} {path}: {detail}") from None
    except urllib.error.URLError as e:
        raise ApifyError(f"network error on {method} {path}: {e.reason}") from None
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ApifyError(f"non-JSON response on {method} {path}") from None


def start_run(actor: str, run_input: dict, *, timeout_s: int = DEFAULT_TIMEOUT_S, memory_mb: int | None = None) -> dict:
    """Start an actor run. Returns {"run_id", "dataset_id", "status"}."""
    bad = forbidden_input_keys(run_input)
    if bad:
        raise ApifyError(f"refusing to run {actor}: input carries session credential keys {bad}")
    params = {"timeout": timeout_s}
    if memory_mb:
        params["memory"] = memory_mb
    resp = _request("POST", f"/acts/{actor_path(actor)}/runs", params=params, body=run_input)
    data = resp.get("data", {}) if isinstance(resp, dict) else {}
    run_id = data.get("id")
    if not run_id:
        raise ApifyError(f"run start returned no id: {json.dumps(resp)[:200]}")
    return {"run_id": run_id, "dataset_id": data.get("defaultDatasetId"), "status": data.get("status")}


def get_run(run_id: str) -> dict:
    resp = _request("GET", f"/actor-runs/{run_id}")
    return resp.get("data", {}) if isinstance(resp, dict) else {}


def wait_for_run(
    run_id: str, *, poll_s: int = DEFAULT_POLL_S, max_wait_s: int = DEFAULT_TIMEOUT_S, sleep=time.sleep
) -> dict:
    """Poll until the run reaches a terminal status. Raises unless SUCCEEDED."""
    waited = 0
    while True:
        data = get_run(run_id)
        status = data.get("status")
        if status in TERMINAL_STATUSES:
            if status != "SUCCEEDED":
                raise ApifyError(f"run {run_id} ended with status {status}")
            return data
        if waited >= max_wait_s:
            raise ApifyError(f"run {run_id} still {status!r} after {max_wait_s}s")
        sleep(poll_s)
        waited += poll_s


def fetch_items(dataset_id: str, *, max_items: int, page: int = PAGE_SIZE) -> list:
    """Fetch up to max_items clean items from a dataset, paging by `page`."""
    items: list = []
    offset = 0
    while len(items) < max_items:
        limit = min(page, max_items - len(items))
        batch = _request(
            "GET",
            f"/datasets/{dataset_id}/items",
            params={"format": "json", "clean": "true", "limit": limit, "offset": offset},
        )
        if not isinstance(batch, list):
            raise ApifyError(f"dataset items response was not a list: {json.dumps(batch)[:200]}")
        items.extend(batch)
        if len(batch) < limit:
            break
        offset += len(batch)
    return items[:max_items]


def run_and_fetch(
    actor: str, run_input: dict, *, max_items: int, timeout_s: int = DEFAULT_TIMEOUT_S, sleep=time.sleep
) -> dict:
    """Start, wait, fetch. Returns {"run_id", "dataset_id", "items"}."""
    started = start_run(actor, run_input, timeout_s=timeout_s)
    finished = wait_for_run(started["run_id"], max_wait_s=timeout_s, sleep=sleep)
    dataset_id = finished.get("defaultDatasetId") or started.get("dataset_id")
    if not dataset_id:
        raise ApifyError(f"run {started['run_id']} has no dataset id")
    items = fetch_items(dataset_id, max_items=max_items)
    return {"run_id": started["run_id"], "dataset_id": dataset_id, "items": items}


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run an Apify actor and fetch its dataset items")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--actor", required=True, help="user/name or user~name")
    run.add_argument("--input-file", required=True, help="JSON file with the actor input")
    run.add_argument("--max-items", type=int, default=150)
    run.add_argument("--out", help="write items here (default: stdout)")
    run.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S)
    run.add_argument("--dry-run", action="store_true", help="print the request; no network")
    args = parser.parse_args(argv)

    try:
        with open(args.input_file) as f:
            run_input = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"error": f"cannot read input file: {e}"}))
        return 1

    bad = forbidden_input_keys(run_input)
    if bad:
        print(json.dumps({"error": f"refused: input carries session credential keys {bad}"}))
        return 1

    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "request": f"POST {API_BASE}/acts/{actor_path(args.actor)}/runs?timeout={args.timeout_s}",
            "input": run_input,
            "max_items": args.max_items,
        }, indent=2))
        return 0

    if not token_present():
        print(json.dumps({"error": "APIFY_API_KEY not set"}))
        return 1

    try:
        result = run_and_fetch(args.actor, run_input, max_items=args.max_items, timeout_s=args.timeout_s)
    except ApifyError as e:
        print(json.dumps({"error": str(e)}))
        return 1

    payload = json.dumps(result["items"], indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(payload)
        summary = {
            "run_id": result["run_id"],
            "dataset_id": result["dataset_id"],
            "items": len(result["items"]),
            "out": args.out,
        }
        print(json.dumps(summary))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
