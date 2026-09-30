#!/usr/bin/env bash
# Append one entry to state/provenance.json and commit it (hash-checked via
# commit-state.sh). Hard rule 5's private half: public-repo commits carry no
# Claude footprint, so this file is the only place that ties a pushed commit
# back to the run, stage, and model that produced it. Call it right after
# every bot push to a product repo (implement.yml open-pr, revise.yml).
#
# Usage: record-provenance.sh <owner/repo> <pr> <branch> <sha> <issue|-> <implement|revise> <round|-> <run-url> [model ...]
set -euo pipefail

REPO="${1:?}"; PR="${2:?}"; BRANCH="${3:?}"; SHA="${4:?}"; ISSUE="${5:?}"; STAGE="${6:?}"; ROUND="${7:?}"; RUN_URL="${8:?}"
shift 8
MODELS=$(printf '%s\n' "$@" | jq -R . | jq -sc .)
FILE=state/provenance.json

[ -f "$FILE" ] || echo '{"entries": []}' > "$FILE"
BEFORE=$(git show "HEAD:$FILE" 2>/dev/null | shasum -a 256 | cut -d' ' -f1 || true)
[ -n "$BEFORE" ] || BEFORE="-"

jq --arg repo "$REPO" --argjson pr "$PR" --arg branch "$BRANCH" --arg sha "$SHA" \
   --arg issue "$ISSUE" --arg stage "$STAGE" --arg round "$ROUND" --arg url "$RUN_URL" \
   --argjson models "$MODELS" --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
   '.entries += [{
      repo: $repo, pr: $pr, branch: $branch, sha: $sha,
      issue: (if $issue == "-" then null else ($issue | tonumber) end),
      stage: $stage,
      round: (if $round == "-" then null else ($round | tonumber) end),
      models: ($models | map(select(. != ""))),
      run_url: $url, at: $at }]' "$FILE" > "$FILE.tmp" && mv "$FILE.tmp" "$FILE"

bash "$(dirname "$0")/commit-state.sh" "$FILE" "$BEFORE" "provenance: $STAGE ${REPO##*/}#$PR @ ${SHA:0:7}"
