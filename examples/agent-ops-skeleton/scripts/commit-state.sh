#!/usr/bin/env bash
# Hash-checked, race-safe commit for state/ files.
#
# Optimistic concurrency: the caller records the sha256 of the state file
# BEFORE modifying it. If another run changed the file in the meantime, the
# committed copy no longer matches that hash and we abort instead of
# clobbering. Push races against main are retried with rebase; a rebase
# conflict on the same state file also aborts (the optimistic check, enforced
# by git itself).
#
# Usage: commit-state.sh <file> <expected-sha256-before-edit | -> <commit-message>
set -euo pipefail

FILE="$1"
EXPECTED="$2"
MSG="$3"

[ -f "$FILE" ] || { echo "ERROR: $FILE not found" >&2; exit 1; }

if [ "$EXPECTED" != "-" ]; then
  COMMITTED=$(git show "HEAD:$FILE" 2>/dev/null | shasum -a 256 | cut -d' ' -f1 || true)
  if [ -n "$COMMITTED" ] && [ "$COMMITTED" != "$EXPECTED" ]; then
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
  if ! git pull --rebase origin main; then
    echo "ERROR: rebase conflict on $FILE — concurrent writer won. Aborting." >&2
    git rebase --abort || true
    exit 2
  fi
  sleep $((i * 2))
done
echo "ERROR: push failed after 5 attempts" >&2
exit 1
