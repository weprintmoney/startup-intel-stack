#!/usr/bin/env bash
# Block target-prospect names from leaving the pipeline in ticket text.
#
# The name list lives in <YOUR_ORG>/sales-ops (guards/prospect-names.txt) and
# is fetched at run time — it must NEVER be committed to this repo or appear
# in logs (a blocklist of prospects IS the target-prospect list). On a hit we
# report the list line number, not the name.
#
# Usage: prospect-name-scan.sh <names-file> <text-file> [<text-file>...]
# Exit 0 = clean; 1 = hit(s); 2 = names file missing/empty-of-entries is the
# caller's fail-closed problem (we only require it to exist here).
set -euo pipefail

NAMES="${1:?usage: prospect-name-scan.sh <names-file> <text-file>...}"
shift
[ -f "$NAMES" ] || { echo "ERROR: names file not found (fail closed)" >&2; exit 2; }

HITS=0
LINENO_N=0
while IFS= read -r name; do
  LINENO_N=$((LINENO_N + 1))
  case "$name" in ''|'#'*) continue ;; esac
  for f in "$@"; do
    if grep -i -q -F -- "$name" "$f"; then
      echo "BLOCKED: $f matches prospect-names.txt line $LINENO_N" >&2
      HITS=$((HITS + 1))
    fi
  done
done < "$NAMES"

if [ "$HITS" -gt 0 ]; then
  exit 1
fi
echo "prospect-name-scan: clean ($# file(s))"
