#!/usr/bin/env bash
# Update one claim in state/queue.json (race-safe via commit-state.sh).
# Every pipeline stage records its transition through this script so the
# queue is always the single source of truth for where a ticket is.
#
# Usage: IMPL_REPO=<YOUR_ORG>/<repo> update-claim.sh <issue> <status> [json-patch]
#   e.g. update-claim.sh 101 spec-pending '{"spec_path":"07-.../101-x.md"}'
#        update-claim.sh 101 spec-approved '{"spec_fast_path":true}'
#        update-claim.sh 101 abandoned '{"abandoned_reason":"build failed twice"}'
#        update-claim.sh 101 - '{"claim_verification":"verified"}'   # "-" keeps the status, patch only
#
# A claim is identified by (issue, impl_repo), not issue alone: one ticket can
# fan out to a claim per repo (an SDK change lands in py, js and go), and each
# runs its own spec/implement/review cycle. Matching on issue alone would drag
# all three through one stage's transition.
#
# If more than one row carries the same key (a stale terminal row beside a
# re-claim), the transition resolves against the one
# non-terminal row; with no single live row it takes the most recent. Reading
# .status across both rows newline-joined them into a FROM that matched
# nothing in transitions.json and every transition failed as illegal.
set -euo pipefail

ISSUE="${1:?usage: update-claim.sh <issue> <status> [json-patch]}"
STATUS="${2:?usage: update-claim.sh <issue> <status> [json-patch]}"
PATCH="${3:-"{}"}"
: "${IMPL_REPO:?IMPL_REPO required (owner/repo the claim implements in)}"
QUEUE=state/queue.json

# Every transition runs under state-retry.sh: a lost queue.json race re-runs
# this script against origin's fresh queue instead of dropping the
# transition. The inner run does the actual work.
if [ -z "${UPDATE_CLAIM_INNER:-}" ]; then
  UPDATE_CLAIM_INNER=1 STATE_RETRY_CONTEXT="claim #$ISSUE ($IMPL_REPO) -> $STATUS" \
    exec bash "$(dirname "$0")/state-retry.sh" "$QUEUE" bash "$0" "$@"
fi
TRANSITIONS="$(dirname "$0")/../state/transitions.json"

jq -e --argjson issue "$ISSUE" --arg repo "$IMPL_REPO" \
  'any(.claims[]; .issue == $issue and .impl_repo == $repo)' "$QUEUE" >/dev/null \
  || { echo "ERROR: no claim for issue #$ISSUE in $IMPL_REPO ($QUEUE)" >&2; exit 1; }

# Index of the one row this call acts on (see header).
TARGET=$(jq --argjson issue "$ISSUE" --arg repo "$IMPL_REPO" --slurpfile t "$TRANSITIONS" '
  ($t[0] | to_entries | map(select(.value | length == 0) | .key)) as $terminal
  | [.claims | to_entries[] | select(.value.issue == $issue and .value.impl_repo == $repo)] as $rows
  | [$rows[] | select(.value.status as $s | ($terminal | index($s)) == null)] as $live
  | if ($live | length) == 1 then $live[0].key else $rows[-1].key end' "$QUEUE")

# "-" is a patch-only call (status unchanged) and skips transition
# enforcement entirely — there is no "from -> from" edge to check.
if [ "$STATUS" != "-" ]; then
  FROM=$(jq -r --argjson idx "$TARGET" '.claims[$idx].status' "$QUEUE")
  if ! jq -e --arg from "$FROM" --arg to "$STATUS" \
    '(.[$from] // []) | index($to) != null' "$TRANSITIONS" >/dev/null; then
    echo "ERROR: illegal transition '$FROM' -> '$STATUS' for issue #$ISSUE ($IMPL_REPO)." \
         "Allowed from '$FROM': $(jq -c --arg from "$FROM" '.[$from] // []' "$TRANSITIONS")" >&2
    exit 1
  fi
fi

BEFORE=$(git show "HEAD:$QUEUE" | shasum -a 256 | cut -d' ' -f1)
# Terminal transitions stamp closed_at (unless the patch supplies one) so the
# retention sweep in pr-merged-reap.yml has a date to age them by.
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
jq --argjson idx "$TARGET" --arg status "$STATUS" --argjson patch "$PATCH" --arg now "$NOW" \
  '.claims[$idx] |= (. + (if $status == "-" then {} else {status: $status} end) + $patch
                       + (if ($status | IN("merged","abandoned")) and (($patch.closed_at // "") == "") then {closed_at: $now} else {} end))' \
  "$QUEUE" > "$QUEUE.tmp" && mv "$QUEUE.tmp" "$QUEUE"

if [ "$STATUS" = "-" ]; then
  MSG="claim #$ISSUE ($IMPL_REPO): $(jq -r 'keys | join(", ")' <<<"$PATCH") updated"
else
  MSG="claim #$ISSUE ($IMPL_REPO) -> $STATUS"
fi
bash "$(dirname "$0")/commit-state.sh" "$QUEUE" "$BEFORE" "$MSG"
