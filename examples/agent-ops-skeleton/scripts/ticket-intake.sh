#!/usr/bin/env bash
# Deterministic ticket intake — stage 1 of the coding loop, no LLM.
# Humans select tickets by labeling them agent:queued (D4: the agent never
# self-selects until L4). This script:
#   1. refuses agent:queued tickets that aren't mode:claude-led
#      (explanatory comment + remove agent:queued — fail closed)
#   2. enforces the WIP cap from state/queue.json
#   3. claims eligible tickets: schema-shaped queue entry, race-safe commit
#      via commit-state.sh, claim comment on the issue
#   4. prints "CLAIM <issue> <branch>" lines for the caller to dispatch
#      spec-draft.yml per claim
#
# Env: PRODUCT_REPO (owner/repo), RUN_URL, GH_TOKEN (issues rw on product repo).
set -euo pipefail

: "${PRODUCT_REPO:?PRODUCT_REPO required}"
: "${RUN_URL:?RUN_URL required}"

QUEUE=state/queue.json
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BEFORE=$(git show "HEAD:$QUEUE" | shasum -a 256 | cut -d' ' -f1)

WIP_CAP=$(jq -r '.wip_cap' "$QUEUE")
ACTIVE=$(jq '[.claims[] | select(.status != "merged" and .status != "abandoned")]' "$QUEUE")
ACTIVE_COUNT=$(jq 'length' <<<"$ACTIVE")
SLOTS=$((WIP_CAP - ACTIVE_COUNT))
echo "WIP: $ACTIVE_COUNT/$WIP_CAP active claims — $SLOTS open slot(s)"

# Open agent:queued issues; the issues API also returns PRs, drop them.
CANDIDATES=$(gh api --paginate "repos/$PRODUCT_REPO/issues?labels=agent:queued&state=open&per_page=100" \
  --jq '.[] | select(has("pull_request") | not) | {number, title, labels: [.labels[].name]}' | jq -s '.')
echo "Candidates: $(jq 'length' <<<"$CANDIDATES") open agent:queued issue(s)"

refuse() { # <issue> <reason-markdown>
  gh api -X POST "repos/$PRODUCT_REPO/issues/$1/comments" -f body="$2" >/dev/null
  gh api -X DELETE "repos/$PRODUCT_REPO/issues/$1/labels/agent%3Aqueued" >/dev/null || true
  echo "REFUSED #$1"
}

CLAIMED=0
while IFS= read -r row; do
  [ -z "$row" ] && continue
  num=$(jq -r '.number' <<<"$row")
  title=$(jq -r '.title' <<<"$row")
  labels=$(jq -r '.labels[]' <<<"$row")

  if grep -qx 'mode:requires-expertise' <<<"$labels" || grep -qx 'mode:mixed' <<<"$labels"; then
    refuse "$num" "This ticket is \`mode:requires-expertise\` or \`mode:mixed\` — the coding agent must not take it (expertise firewall, \`08-team-culture/coding-agents.md\`). Removed \`agent:queued\`. If part of this is delegable, split that part into its own \`mode:claude-led\` ticket."
    continue
  fi
  if ! grep -qx 'mode:claude-led' <<<"$labels"; then
    refuse "$num" "This ticket has \`agent:queued\` but no \`mode:claude-led\` label — intake only claims explicitly claude-led tickets. Removed \`agent:queued\`; re-add both labels once the mode is set."
    continue
  fi
  if jq -e --argjson n "$num" 'any(.[]; .issue == $n)' <<<"$ACTIVE" >/dev/null; then
    echo "SKIP #$num: already claimed"
    continue
  fi
  if [ "$(gh api "repos/$PRODUCT_REPO/git/matching-refs/heads/agent/$num-" --jq 'length')" -gt 0 ]; then
    echo "::warning::SKIP #$num: agent/$num-* branch exists with no active claim — investigate before re-queuing"
    continue
  fi
  if [ "$CLAIMED" -ge "$SLOTS" ]; then
    echo "SKIP #$num: WIP cap reached"
    continue
  fi

  slug=$(tr '[:upper:]' '[:lower:]' <<<"$title" | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-40 | sed -E 's/-+$//')
  [ -n "$slug" ] || slug=ticket
  branch="agent/$num-$slug"
  class=$( (grep -m1 '^class:' <<<"$labels" || true) | sed 's/^class://')
  [ -n "$class" ] || class=unclassified

  claim=$(jq -n --argjson issue "$num" --arg repo "$PRODUCT_REPO" --arg title "$title" \
    --arg class "$class" --arg at "$NOW" --arg run "$RUN_URL" --arg branch "$branch" \
    '{issue: $issue, repo: $repo, title: $title, mode: "claude-led", ticket_class: $class,
      claimed_at: $at, run_url: $run, branch: $branch, status: "claimed"}')
  jq --argjson c "$claim" '.claims += [$c]' "$QUEUE" > "$QUEUE.tmp" && mv "$QUEUE.tmp" "$QUEUE"

  gh api -X POST "repos/$PRODUCT_REPO/issues/$num/comments" \
    -f body="Claimed by agent-ops ([run]($RUN_URL)). Branch: \`$branch\`. Next stage: spec draft." >/dev/null
  echo "CLAIM $num $branch"
  CLAIMED=$((CLAIMED + 1))
done < <(jq -c '.[]' <<<"$CANDIDATES")

if [ "$CLAIMED" -gt 0 ]; then
  bash scripts/commit-state.sh "$QUEUE" "$BEFORE" "intake: claim $CLAIMED ticket(s)"
else
  echo "No new claims."
fi
