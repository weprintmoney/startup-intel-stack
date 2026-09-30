#!/usr/bin/env bash
# Parse the terminal `RESULT:` (or `VERDICT:`) line a pipeline node prints.
#
# Every node ends with exactly one `RESULT: <TOKEN> [detail]` line and the
# workflows branch on TOKEN. Models wrap that line in markdown often enough
# that a wrapper-strip fix added -- `sed 's/[`*_]//g'` -- which also
# deleted the underscore INSIDE every token: SPEC_PR read as SPECPR,
# FAST_PATH as FASTPATH, DEPENDENCY_BLOCKED as DEPENDENCYBLOCKED, and the
# `case` fell through to "No RESULT line from spec-drafter" (two good spec PRs
# opened, six red runs, both claims abandoned). One parser, one test file (result-line_test.sh), every site.
#
# Usage:
#   result-line.sh <stream.jsonl> [LABEL]            last `result` entry of a claude -p stream-json file
#   result-line.sh --text <file> [LABEL]             a plain text file (e.g. review.md)
#   result-line.sh [--text] --first <file> [LABEL]   first matching line wins instead of the last
# LABEL defaults to RESULT. Prints two lines shaped for `>> "$GITHUB_OUTPUT"`:
#   result=<TOKEN>          empty when no line matched
#   result_detail=<rest>    the remainder of that line, one line, <=300 chars
#
# Rules: markdown emphasis (backticks, asterisks) is stripped anywhere;
# underscores are stripped only at the edges of a whitespace-delimited word,
# never inside a token; a leading list bullet or blockquote marker is
# tolerated; the label must start the cleaned line; the LAST matching line
# wins (a model that mentions "RESULT:" in prose and then ends properly still
# parses) unless --first is given (review.md's contract is line one).
set -euo pipefail

MODE=stream
PICK=last
while [ $# -gt 0 ]; do
  case "$1" in
    --text) MODE=text; shift ;;
    --first) PICK=first; shift ;;
    *) break ;;
  esac
done
SRC="${1:?usage: result-line.sh [--text] [--first] <file> [LABEL]}"
LABEL="${2:-RESULT}"

if [ "$MODE" = "stream" ]; then
  TEXT=$(jq -rs '[.[] | select(.type? == "result")] | last | .result // ""' "$SRC" 2>/dev/null || true)
else
  TEXT=$(cat "$SRC" 2>/dev/null || true)
fi

CLEAN=$(printf '%s\n' "$TEXT" \
  | sed -E 's/[`*]//g; s/(^|[[:space:]])_+/\1/g; s/_+([[:space:]]|$)/\1/g; s/^[[:space:]]*([->]+[[:space:]]+)?//')

if [ "$PICK" = "first" ]; then
  LINE=$(grep -E "^${LABEL}:[[:space:]]*[A-Za-z]" <<<"$CLEAN" | head -1 || true)
else
  LINE=$(grep -E "^${LABEL}:[[:space:]]*[A-Za-z]" <<<"$CLEAN" | tail -1 || true)
fi

TOKEN=""; DETAIL=""
if [ -n "$LINE" ]; then
  REST=${LINE#"${LABEL}:"}
  REST=$(sed -E 's/^[[:space:]]+//' <<<"$REST")
  TOKEN=$(awk '{print $1}' <<<"$REST" | sed -E 's/[^A-Za-z0-9_-]+$//')
  DETAIL=$(sed -E 's/^[^[:space:]]+[[:space:]]*//' <<<"$REST" | tr -d '\r\n' | sed -E 's/[[:space:]]+$//' | cut -c1-300)
fi
printf 'result=%s\n' "$TOKEN"
printf 'result_detail=%s\n' "$DETAIL"
