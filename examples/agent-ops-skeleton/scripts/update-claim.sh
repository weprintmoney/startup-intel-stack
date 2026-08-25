#!/usr/bin/env bash
# Update one claim in state/queue.json (race-safe via commit-state.sh).
# Every pipeline stage records its transition through this script so the
# queue is always the single source of truth for where a ticket is.
#
# Usage: update-claim.sh <issue> <status> [json-patch]
#   e.g. update-claim.sh 101 spec-pending '{"spec_path":"07-.../101-x.md"}'
#        update-claim.sh 101 spec-approved '{"spec_fast_path":true}'
#        update-claim.sh 101 abandoned '{"abandoned_reason":"build failed twice"}'
set -euo pipefail

ISSUE="${1:?usage: update-claim.sh <issue> <status> [json-patch]}"
STATUS="${2:?usage: update-claim.sh <issue> <status> [json-patch]}"
PATCH="${3:-"{}"}"
QUEUE=state/queue.json

jq -e --argjson issue "$ISSUE" 'any(.claims[]; .issue == $issue)' "$QUEUE" >/dev/null \
  || { echo "ERROR: no claim for issue #$ISSUE in $QUEUE" >&2; exit 1; }

BEFORE=$(git show "HEAD:$QUEUE" | shasum -a 256 | cut -d' ' -f1)
jq --argjson issue "$ISSUE" --arg status "$STATUS" --argjson patch "$PATCH" \
  '.claims |= map(if .issue == $issue then . + {status: $status} + $patch else . end)' \
  "$QUEUE" > "$QUEUE.tmp" && mv "$QUEUE.tmp" "$QUEUE"

bash "$(dirname "$0")/commit-state.sh" "$QUEUE" "$BEFORE" "claim #$ISSUE -> $STATUS"
