#!/usr/bin/env bash
# Hash-checked, race-safe commit for state/ files.
#
# Optimistic concurrency: the caller records the sha256 of the state file
# BEFORE modifying it. If another run changed the file in the meantime, the
# committed copy no longer matches that hash and we abort instead of
# clobbering. Push races against main are retried with rebase; a rebase
# conflict on the same state file also aborts (the optimistic check, enforced
# by git itself). Exit 2 means "lost the race, nothing pushed": callers that
# must not drop the write run under scripts/state-retry.sh, which resyncs and
# re-runs them against fresh state.
#
# Usage: commit-state.sh <file> <expected-sha256-before-edit | -> <commit-message>
set -euo pipefail

FILE="$1"
EXPECTED="$2"
MSG="$3"

[ -f "$FILE" ] || { echo "ERROR: $FILE not found" >&2; exit 1; }

if [ "$EXPECTED" != "-" ]; then
  # Fail closed: an unreadable HEAD copy used to empty
  # $COMMITTED and skip the check, so "hash-checked" was best-effort. A
  # caller writing a file that is new at HEAD passes "-" explicitly.
  if ! HEAD_COPY=$(git show "HEAD:$FILE" 2>/dev/null); then
    echo "ERROR: cannot read HEAD:$FILE to check its hash — refusing to write blind (pass '-' for a new file)." >&2
    exit 2
  fi
  COMMITTED=$(printf '%s\n' "$HEAD_COPY" | shasum -a 256 | cut -d' ' -f1)
  if [ "$COMMITTED" != "$EXPECTED" ]; then
    echo "ERROR: $FILE changed under us (expected $EXPECTED, HEAD has $COMMITTED). Re-read state and retry." >&2
    exit 2
  fi
fi

python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$FILE" || { echo "ERROR: $FILE is not valid JSON" >&2; exit 1; }

git add "$FILE"
if git diff --staged --quiet; then
  echo "No changes to commit for $FILE"
  exit 0
fi
git commit -m "$MSG"

for i in 1 2 3 4 5; do
  if git push; then exit 0; fi
  echo "Push rejected (attempt $i/5); rebasing on origin/main..."
  # The rebase IS the second half of the optimistic check: a concurrent
  # writer of the same file conflicts here and we abort rather than merge
  # two jq rewrites of one JSON document.
  if ! git pull --rebase origin main; then
    echo "ERROR: rebase conflict on $FILE — concurrent writer won. Aborting." >&2
    git rebase --abort || true
    exit 2
  fi
  sleep $((i * 2))
done
echo "ERROR: push failed after 5 attempts" >&2
exit 1
