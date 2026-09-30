#!/usr/bin/env bash
# Prints token usage + cost from Claude Code output files (stream-json JSONL
# or single-object json) to the job log: one line per file, then a per-model
# breakdown and totals aggregated across all files. Per-node cost visibility
# — decomposes the org-level cost-digest number into pipeline stages.
# Never fails the job: missing/unparseable files log a note and are skipped.
#
# Usage: log-token-usage.sh <file> [more files...]

set -u

if [ $# -lt 1 ]; then
  echo "log-token-usage: no files given"
  exit 0
fi

RESULTS=$(mktemp)
trap 'rm -f "$RESULTS"' EXIT

for f in "$@"; do
  if [ ! -s "$f" ]; then
    echo "log-token-usage: $f missing or empty — skipped"
    continue
  fi
  ENTRY=$(jq -cs '[.[] | select(.type? == "result")] | last // empty' "$f" 2>/dev/null)
  if [ -z "$ENTRY" ]; then
    echo "log-token-usage: $f has no result entry — skipped"
    continue
  fi
  echo "$ENTRY" >> "$RESULTS"
  jq -r --arg f "$(basename "$f")" \
    '"\($f): in=\(.usage.input_tokens // 0) out=\(.usage.output_tokens // 0) cache_create=\(.usage.cache_creation_input_tokens // 0) cache_read=\(.usage.cache_read_input_tokens // 0) turns=\(.num_turns // "?") cost_usd=\(.total_cost_usd // 0)"' \
    <<<"$ENTRY"
done

if [ ! -s "$RESULTS" ]; then
  echo "log-token-usage: no usable results"
  exit 0
fi

echo "=== Token usage by model ==="
jq -rs '
  [.[] | (.modelUsage // {}) | to_entries[]]
  | group_by(.key)[]
  | {model: .[0].key,
     in: ([.[].value.inputTokens // 0] | add),
     out: ([.[].value.outputTokens // 0] | add),
     cc: ([.[].value.cacheCreationInputTokens // 0] | add),
     cr: ([.[].value.cacheReadInputTokens // 0] | add),
     cost: ([.[].value.costUSD // 0] | add)}
  | "\(.model): in=\(.in) out=\(.out) cache_create=\(.cc) cache_read=\(.cr) cost_usd=\(.cost)"
' "$RESULTS"

echo "=== Totals ==="
jq -rs '
  {in: ([.[].usage.input_tokens // 0] | add),
   out: ([.[].usage.output_tokens // 0] | add),
   cc: ([.[].usage.cache_creation_input_tokens // 0] | add),
   cr: ([.[].usage.cache_read_input_tokens // 0] | add),
   cost: ([.[].total_cost_usd // 0] | add),
   turns: ([.[].num_turns // 0] | add),
   runs: length}
  | "runs=\(.runs) in=\(.in) out=\(.out) cache_create=\(.cc) cache_read=\(.cr) total_tokens=\(.in + .out + .cc + .cr) turns=\(.turns) cost_usd=\(.cost)"
' "$RESULTS"

exit 0
