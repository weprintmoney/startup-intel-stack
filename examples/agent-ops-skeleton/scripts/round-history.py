#!/usr/bin/env python3
"""Round history for the bounded judge -> revise -> re-judge loop.

The loop's only state is one machine-readable block in the product PR's body:

    <!-- agent-ops:rounds:start -->
    ## Judge / revise rounds
    | Round | Stage | Verdict | Score | Cost (USD) | Commit | Run |
    ...
    Total ... of the ... ceiling ...
    <!-- agent-ops:rounds:data {"cap": 3, "ceiling_usd": 50.0, "rounds": [...]} -->
    <!-- agent-ops:rounds:end -->

Humans see the table; the workflows read the JSON. Re-dispatching a round
replaces its entry (idempotent on (round, stage)), so a manual re-judge never
double-counts. Cost is the CLI's own estimate (`total_cost_usd` from each
node's stream-json result entry) summed over implement + every round; the
per-ticket ceiling is checked against that sum. Same idempotent-block idea as
`verify-claims.py patch-body`.

Subcommands (all take --body FILE, the PR body as a text file):
  read                           print the payload JSON
  append --entry JSON            add or replace one entry; rewrite the block in place
  next-round                     1 + highest judge round recorded (1 when none)
  total-cost                     sum of cost_usd over all entries, 2 decimals
  decide --round N --verdict pass|fail|rejected [--cap N] [--ceiling USD]
                                 -> judge-pass | revise | needs-human:cap | needs-human:cost | halt:rejected-verdict
  summary                        one line per entry, oldest first (for Slack)

Entry: {"round": int>=0, "stage": "implement"|"judge"|"revise",
        "verdict": "pass"|"fail"|"rejected"|null, "score": int|null,
        "cost_usd": number>=0, "sha": str, "run_url": str, "at": ISO-8601, "note": str}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

START = "<!-- agent-ops:rounds:start -->"
END = "<!-- agent-ops:rounds:end -->"
DATA_RE = re.compile(r"<!-- agent-ops:rounds:data (.*?) -->", re.S)
BLOCK_RE = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)

STAGES = ("implement", "judge", "revise")
VERDICTS = ("pass", "fail", "rejected", None)
DEFAULT_CAP = 3
DEFAULT_CEILING = 50.0


# --------------------------------------------------------------------- io ---

def read_payload(body: str) -> dict:
    m = DATA_RE.search(body)
    if not m:
        return {"cap": DEFAULT_CAP, "ceiling_usd": DEFAULT_CEILING, "rounds": []}
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise SystemExit(f"round block data is not valid JSON: {e}") from e
    data.setdefault("cap", DEFAULT_CAP)
    data.setdefault("ceiling_usd", DEFAULT_CEILING)
    data.setdefault("rounds", [])
    return data


def validate_entry(e: dict) -> dict:
    if not isinstance(e, dict):
        raise SystemExit("entry must be a JSON object")
    out = dict(e)
    if not isinstance(out.get("round"), int) or out["round"] < 0:
        raise SystemExit("entry.round must be an integer >= 0")
    if out.get("stage") not in STAGES:
        raise SystemExit(f"entry.stage must be one of {STAGES}")
    out.setdefault("verdict", None)
    if out["verdict"] not in VERDICTS:
        raise SystemExit(f"entry.verdict must be one of {VERDICTS}")
    out.setdefault("score", None)
    if out["score"] is not None and not isinstance(out["score"], int):
        raise SystemExit("entry.score must be an integer or null")
    cost = out.get("cost_usd", 0)
    if not isinstance(cost, (int, float)) or cost < 0:
        raise SystemExit("entry.cost_usd must be a number >= 0")
    out["cost_usd"] = round(float(cost), 4)
    out["sha"] = str(out.get("sha") or "")
    out["run_url"] = str(out.get("run_url") or "")
    out.setdefault("note", "")
    out["at"] = str(out.get("at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    return out


def sort_key(e: dict):
    return (e["round"], STAGES.index(e["stage"]))


# ------------------------------------------------------------------ render ---

def _fmt(v, dash="—"):
    return dash if v in (None, "") else str(v)


def render(payload: dict) -> str:
    rounds = sorted(payload["rounds"], key=sort_key)
    total = sum(e["cost_usd"] for e in rounds)
    lines = [START, "## Judge / revise rounds", "",
             "| Round | Stage | Verdict | Score | Cost (USD) | Commit | Run |",
             "|---|---|---|---|---|---|---|"]
    for e in rounds:
        sha = e["sha"][:7] if e["sha"] else "—"
        run = f"[run]({e['run_url']})" if e["run_url"] else "—"
        lines.append(f"| {e['round']} | {e['stage']} | {_fmt(e['verdict'])} | {_fmt(e['score'])} "
                     f"| {e['cost_usd']:.2f} | `{sha}` | {run} |")
    judge_rounds = [e["round"] for e in rounds if e["stage"] == "judge"]
    lines += ["",
              f"Total ${total:.2f} of the ${payload['ceiling_usd']:.2f} per-ticket ceiling · "
              f"judge round {max(judge_rounds) if judge_rounds else 0} of {payload['cap']} · "
              "bounded loop per `CLAUDE.md` rule 8 (agent-ops)."]
    # '>' escaped so the JSON can never terminate the HTML comment early.
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).replace(">", "\\u003e")
    lines += [f"<!-- agent-ops:rounds:data {data} -->", END]
    return "\n".join(lines)


def write_block(body: str, block: str) -> str:
    if BLOCK_RE.search(body):
        return BLOCK_RE.sub(lambda _m: block, body)
    body = body.rstrip()
    return (body + "\n\n" if body else "") + block + "\n"


# --------------------------------------------------------------- commands ---

def cmd_read(args):
    print(json.dumps(read_payload(Path(args.body).read_text()), indent=2))
    return 0


def cmd_append(args):
    p = Path(args.body)
    body = p.read_text() if p.is_file() else ""
    payload = read_payload(body)
    if args.cap is not None:
        payload["cap"] = args.cap
    if args.ceiling is not None:
        payload["ceiling_usd"] = float(args.ceiling)
    entry = validate_entry(json.loads(args.entry))
    payload["rounds"] = [e for e in payload["rounds"]
                         if not (e["round"] == entry["round"] and e["stage"] == entry["stage"])]
    payload["rounds"].append(entry)
    payload["rounds"].sort(key=sort_key)
    p.write_text(write_block(body, render(payload)))
    print(f"recorded round {entry['round']} {entry['stage']} "
          f"({_fmt(entry['verdict'], 'no verdict')}, ${entry['cost_usd']:.2f}); "
          f"total ${sum(e['cost_usd'] for e in payload['rounds']):.2f}")
    return 0


def next_round(payload: dict) -> int:
    judged = [e["round"] for e in payload["rounds"] if e["stage"] == "judge"]
    return (max(judged) + 1) if judged else 1


def cmd_next_round(args):
    print(next_round(read_payload(Path(args.body).read_text())))
    return 0


def total_cost(payload: dict) -> float:
    return round(sum(e["cost_usd"] for e in payload["rounds"]), 2)


def cmd_total_cost(args):
    print(f"{total_cost(read_payload(Path(args.body).read_text())):.2f}")
    return 0


def decide(payload: dict, rnd: int, verdict: str, cap: int | None = None, ceiling: float | None = None) -> str:
    cap = payload["cap"] if cap is None else cap
    ceiling = payload["ceiling_usd"] if ceiling is None else ceiling
    if verdict == "rejected":
        return "halt:rejected-verdict"
    if verdict == "pass":
        return "judge-pass"
    if verdict != "fail":
        raise SystemExit(f"verdict must be pass|fail|rejected, got {verdict!r}")
    if rnd >= cap:
        return "needs-human:cap"
    if total_cost(payload) >= ceiling:
        return "needs-human:cost"
    return "revise"


def cmd_decide(args):
    payload = read_payload(Path(args.body).read_text())
    print(decide(payload, args.round, args.verdict, args.cap, args.ceiling))
    return 0


def cmd_summary(args):
    payload = read_payload(Path(args.body).read_text())
    rounds = sorted(payload["rounds"], key=sort_key)
    if not rounds:
        print("(no rounds recorded)")
        return 0
    for e in rounds:
        bits = [f"round {e['round']} {e['stage']}"]
        if e["verdict"]:
            bits.append(e["verdict"] + (f" {e['score']}/100" if e["score"] is not None else ""))
        bits.append(f"${e['cost_usd']:.2f}")
        if e["sha"]:
            bits.append(e["sha"][:7])
        if e["run_url"]:
            bits.append(e["run_url"])
        print(" · ".join(bits))
    print(f"total ${total_cost(payload):.2f} / ${payload['ceiling_usd']:.2f} ceiling, cap {payload['cap']}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--body", required=True, help="PR body text file")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("read").set_defaults(fn=cmd_read)
    a = sub.add_parser("append")
    a.add_argument("--entry", required=True, help="JSON object")
    a.add_argument("--cap", type=int)
    a.add_argument("--ceiling", type=float)
    a.set_defaults(fn=cmd_append)
    sub.add_parser("next-round").set_defaults(fn=cmd_next_round)
    sub.add_parser("total-cost").set_defaults(fn=cmd_total_cost)
    d = sub.add_parser("decide")
    d.add_argument("--round", type=int, required=True)
    d.add_argument("--verdict", required=True, choices=["pass", "fail", "rejected"])
    d.add_argument("--cap", type=int)
    d.add_argument("--ceiling", type=float)
    d.set_defaults(fn=cmd_decide)
    sub.add_parser("summary").set_defaults(fn=cmd_summary)
    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
