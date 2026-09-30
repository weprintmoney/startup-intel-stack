#!/usr/bin/env bash
# Re-read-and-retry for state/ writers.
#
# commit-state.sh is the optimistic check: when a concurrent writer changed
# the same state file, the push-race rebase conflicts and it exits 2
# ("concurrent writer won"). That is correct — two jq rewrites of one JSON
# document must never be merged by git — but a transition that loses the
# race must not be dropped either. Once, spec-draft
# opened its spec PR, lost the queue.json race to two intake runs, left the
# claim at `claimed`, and the orchestrator drafted the ticket a second time.
#
# This wrapper owns the retry commit-state.sh's error text asks for: on exit
# 2 it discards the losing local commit, resyncs the state file to
# origin/main, and re-runs the writer from scratch so it re-reads the fresh
# state, re-validates (an update-claim.sh transition that became illegal
# exits 1 and is NOT retried), and re-applies. Any exit other than 2 is
# returned as-is. Exhausted retries post a Slack alert and exit 2.
#
# The writer must be a separate process that computes its change from the
# current checkout on every run (update-claim.sh, ticket-intake.sh).
#
# Usage: state-retry.sh <state-file> <command> [args...]
# Env:   STATE_RETRY_ATTEMPTS (default 5), STATE_RETRY_SLEEP (base seconds,
#        default 2; 0 in tests), STATE_RETRY_CONTEXT (text for the alert).
set -euo pipefail

FILE="${1:?usage: state-retry.sh <state-file> <command> [args...]}"
shift
[ "$#" -gt 0 ] || { echo "usage: state-retry.sh <state-file> <command> [args...]" >&2; exit 1; }

ATTEMPTS="${STATE_RETRY_ATTEMPTS:-5}"
BASE="${STATE_RETRY_SLEEP:-2}"

for attempt in $(seq 1 "$ATTEMPTS"); do
  rc=0
  "$@" || rc=$?
  [ "$rc" -eq 2 ] || exit "$rc"

  echo "state-retry: $FILE write lost a race (attempt $attempt/$ATTEMPTS); resyncing to origin/main and re-applying." >&2
  [ "$attempt" -lt "$ATTEMPTS" ] || break
  # Drop the unpushed state commit (mixed reset keeps any unrelated
  # working-tree changes a later step still means to commit), then take
  # origin's copy of the state file so the writer re-reads fresh state.
  git fetch -q origin main
  git reset -q origin/main
  git checkout -q origin/main -- "$FILE"
  if [ "$BASE" != "0" ]; then sleep $((attempt * BASE + RANDOM % (BASE + 1))); fi
done

bash "$(dirname "$0")/slack-alert.sh" \
  ":rotating_light: agent-ops: $FILE write dropped after $ATTEMPTS attempts — ${STATE_RETRY_CONTEXT:-$*}. Run: ${RUN_URL:-${GITHUB_SERVER_URL:-}/${GITHUB_REPOSITORY:-}/actions/runs/${GITHUB_RUN_ID:-}}" || true
exit 2
