#!/usr/bin/env bash
# Deterministic expertise firewall: fail when a commit range touches paths
# reserved for human expertise (crypto, key handling, indexing core, query
# path — see internal-docs/08-team-culture/coding-agents.md).
# Never self-policed: runs as a required CI check on agent/* branches.
#
# Guards file: one bash glob per line, matched with `case` semantics where
# '*' crosses '/' (so src/cpu/** matches any depth). Full-line comments and
# blank lines are skipped. No list for a repo = fail closed (the workflow
# enforces that; this script requires the file to exist).
#
# Usage: expertise-path-guard.sh <guards-file> <base-ref> [head-ref]
#
# Diffs against merge-base(base, head), not base's current tip: a two-dot
# `git diff base..head` is a raw tree comparison with no ancestry, so once
# base has moved on since the branch forked, every file base changed in the
# meantime reads as "touched by this branch" too (found live: a
# sandbox-verification PR, forked before four unrelated merges landed on
# guarded paths, failed on files it never touched).
set -euo pipefail

GUARDS="${1:?usage: expertise-path-guard.sh <guards-file> <base-ref> [head-ref]}"
BASE="${2:?usage: expertise-path-guard.sh <guards-file> <base-ref> [head-ref]}"
HEAD_REF="${3:-HEAD}"

[ -f "$GUARDS" ] || { echo "ERROR: guards file '$GUARDS' not found" >&2; exit 1; }

FAILED=0
while IFS= read -r f; do
  while IFS= read -r pat; do
    case "$pat" in ''|\#*) continue ;; esac
    # shellcheck disable=SC2254  # unquoted on purpose: glob match
    case "$f" in
      $pat)
        echo "EXPERTISE PATH: $f (matched '$pat')"
        FAILED=1
        break ;;
    esac
  done < "$GUARDS"
done < <(git diff --name-only "$BASE...$HEAD_REF")

if [ "$FAILED" -ne 0 ]; then
  echo ""
  echo "Expertise-path guard FAILED: this change touches paths reserved for human expertise."
  echo "Route the ticket as mode:requires-expertise instead (08-team-culture/coding-agents.md)."
  exit 1
fi
echo "Expertise-path guard clean: $BASE...$HEAD_REF ($GUARDS)"
