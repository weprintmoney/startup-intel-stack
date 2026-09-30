#!/usr/bin/env bash
# Run one `claude -p` pipeline node and make its failure loud.
#
# Every node used to do `claude -p "$(cat persona)" ... > stream.jsonl` under
# `bash -e`. When the CLI exits non-zero (API 4xx, a missing workspace-id
# header, turn cap, auth), the step aborts on the redirect and the job log
# shows only "exit code 1" -- the reason sits inside the stream file nobody
# printed. Several early failures took a separate dig through the stream to
# diagnose. This wrapper owns the invocation so every node fails the same
# way, once:
#
#   * always requests stream-json (+ --verbose) into <stream-out.jsonl>
#   * always grants /tmp as an extra tool directory -- the pipeline's
#     review-input/review-output convention lives there, and without
#     --add-dir the Read/Write tools are scoped to the cwd, so whether an
#     output file landed depended on the model picking Bash over Write
#   * on non-zero exit: prints the parsed result entry (subtype, is_error,
#     turns, the model's final text), the CLI's stderr, and the raw stream
#     tail inside a log group, then exits with the CLI's code unchanged --
#     callers that treat a node failure as non-fatal keep their `|| ...`
#
# Usage:
#   bash scripts/run-claude.sh <stream-out.jsonl> <prompt> [claude flags...]
#
#   bash scripts/run-claude.sh /tmp/plan.stream.jsonl "$(cat agents/x/CLAUDE.md)
#
#   Task: <one line naming the job>
#   Inputs at: <paths>
#   Write output to: <paths>" \
#     --allowedTools "Bash,Read,Write,Glob,Grep" --model claude-sonnet-4-6 --max-turns 60
#
# The prompt shape (persona, blank line, Task / Inputs at / Write output to)
# is the one the pipeline's working nodes already used (dream.yml miner
# verifier, the two eval runners). Persona-only prompts made the model infer
# the job, and ~1 in 4 runs it answered "no task provided" and stopped.
set -uo pipefail

OUT="${1:?usage: run-claude.sh <stream-out.jsonl> <prompt> [claude flags...]}"
PROMPT="${2:?usage: run-claude.sh <stream-out.jsonl> <prompt> [claude flags...]}"
shift 2
ERR="${OUT%.jsonl}.stderr"

mkdir -p "$(dirname "$OUT")"

# Claude Code appends a "Co-Authored-By: Claude ..." byline to every commit it
# makes unless told not to. Public repos must carry zero footprint (hard rule
# 5; footprint-scan enforces it), and the personas already say "no
# attribution trailers" -- the model still added them (seen in practice). Turn it off at the source for every node; the
# strip-attribution action before the push is the deterministic backstop.
CFG="${HOME:-/root}/.claude/settings.json"
mkdir -p "$(dirname "$CFG")"
if [ -s "$CFG" ]; then
  jq '. + {includeCoAuthoredBy: false, attribution: {commit: "", pr: ""}}' "$CFG" > "$CFG.tmp" && mv "$CFG.tmp" "$CFG"
else
  echo '{"includeCoAuthoredBy": false, "attribution": {"commit": "", "pr": ""}}' > "$CFG"
fi

# Prompt caching. Every call site passes one
# string: the persona, a blank line, then a task block whose first line is
# `Task:` / `Inputs at:` / `Write ... to:` / `End with`. The persona used to
# ride in the user message, and each `claude -p` is a fresh session, so the
# 18.5 KB the founder persona was uncached input on every one of the ~50 weekly eval
# cases. Claude Code marks the system prompt as a cache prefix; appending the
# persona there makes the prefix byte-identical across runs of the same node,
# so it is written once and read from cache on every following run inside the
# TTL. Only the task block stays in the user message. Nothing changes for a
# prompt without that shape. Opt out per call with RUN_CLAUDE_INLINE_PERSONA=1.
if [ -z "${RUN_CLAUDE_INLINE_PERSONA:-}" ]; then
  SPLIT=$(awk 'BEGIN{prev="x"} /^(Task:|Inputs at:|Write (output|verdict|the review|your review)[^:]*:|End with)/ && prev=="" {print NR; exit} {prev=$0}' <<<"$PROMPT")
  if [ -n "$SPLIT" ] && [ "$SPLIT" -gt 2 ]; then
    PERSONA_FILE="${OUT%.jsonl}.persona.md"
    head -n $((SPLIT - 2)) <<<"$PROMPT" > "$PERSONA_FILE"
    PROMPT=$(tail -n +"$SPLIT" <<<"$PROMPT")
    set -- "$@" --append-system-prompt-file "$PERSONA_FILE"
    echo "run-claude: persona ($(wc -c < "$PERSONA_FILE" | tr -d ' ') bytes) appended to the system prompt; task block ($(wc -l <<<"$PROMPT" | tr -d ' ') lines) is the user message"
  fi
fi

claude -p "$PROMPT" "$@" --add-dir /tmp --output-format stream-json --verbose > "$OUT" 2> "$ERR"
RC=$?

if [ "$RC" -ne 0 ]; then
  NAME=$(basename "$OUT")
  echo "::error::claude -p exited $RC ($NAME) — detail in the log group below"
  echo "::group::claude failure detail — $NAME"
  ENTRY=$(jq -cs '[.[] | select(.type? == "result")] | last // empty' "$OUT" 2>/dev/null || true)
  if [ -n "$ENTRY" ]; then
    jq -r '"result entry: subtype=\(.subtype // "?") is_error=\(.is_error // false) turns=\(.num_turns // "?") duration_ms=\(.duration_ms // "?") cost_usd=\(.total_cost_usd // "?")"' <<<"$ENTRY"
    echo "--- final text (first 2000 chars) ---"
    jq -r '(.result // "" | tostring)[0:2000]' <<<"$ENTRY"
  else
    echo "no result entry in the stream — the API rejected the first request, or the CLI died before its first turn"
  fi
  if [ -s "$ERR" ]; then
    echo "--- stderr (last 3000 bytes) ---"
    tail -c 3000 "$ERR"; echo
  fi
  if [ -s "$OUT" ]; then
    echo "--- stream tail (last 3000 bytes) ---"
    tail -c 3000 "$OUT"; echo
  else
    echo "--- stream file is empty ---"
  fi
  echo "::endgroup::"
fi
exit "$RC"
