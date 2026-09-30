#!/usr/bin/env bash
# Deterministic ticket intake — stage 1 of the coding loop, no LLM.
# Humans select tickets by labeling them agent:queued (the agent never
# self-selects until L4). This script:
#   1. refuses agent:queued tickets that aren't mode:claude-led
#      (explanatory comment + remove agent:queued — fail closed)
#   2. routes each ticket to its implementation repo(s) from repo:<name>
#      labels; refuses tickets with no routable target (fail closed)
#   3. enforces the WIP cap from state/queue.json
#   4. claims eligible (ticket, impl-repo) pairs: schema-shaped queue entry,
#      race-safe commit via commit-state.sh; ONLY THEN the status card and
#      the groom:review label drop (side effects used to land
#      before the commit, so a failed commit left tickets commented-as-claimed
#      with no queue entry). Refusals are independent of the queue and stay
#      immediate.
#      The status card (scripts/status-card.py) is the ONE bot comment a
#      claim gets on its ticket: created here, rewritten in place by every
#      later stage. No stage posts a second narrative comment.
#   5. prints "CLAIM <issue> <branch> <repo-short>" lines for the run log.
#      Dispatch is not this script's job: spec-draft-orchestrator.yml fires
#      on the intake workflow's completion and dispatches spec-draft from
#      state/queue.json, one claim at a time.
#
# Two repos, deliberately distinct:
#   TICKET_REPO — where the issue lives. Always example-app-core; team tickets
#                 are filed there whatever repo the work touches.
#   impl repo   — where the branch, code, and PR land. From repo:<name>.
# A ticket carrying three repo: labels fans out to three claims, three
# branches, three PRs — one per repo. Same branch name in each; no collision.
#
# Routing is fail-closed twice over: a repo: label is honoured only if the
# repo is listed in state/impl-repos.json AND has a guards/<repo>.paths
# expertise list. Either missing = refusal, never a silent default to core.
#
# Env: TICKET_REPO (owner/repo), RUN_URL, GH_TOKEN (issues rw on the ticket
#      repo), IMPL_GH_TOKEN (contents read on the impl repos — a separate
#      token so the ticket repo's issues:write is never handed to a public
#      SDK repo).
set -euo pipefail

: "${TICKET_REPO:?TICKET_REPO required}"
: "${IMPL_GH_TOKEN:?IMPL_GH_TOKEN required}"
: "${RUN_URL:?RUN_URL required}"

QUEUE=state/queue.json
ALLOWLIST=state/impl-repos.json
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BEFORE=$(git show "HEAD:$QUEUE" | shasum -a 256 | cut -d' ' -f1)

WIP_CAP=$(jq -r '.wip_cap' "$QUEUE")
ACTIVE=$(jq '[.claims[] | select(.status != "merged" and .status != "abandoned" and .status != "spec-clarify-pending")]' "$QUEUE")
ACTIVE_COUNT=$(jq 'length' <<<"$ACTIVE")
# Parked claims: spec-draft posted one clarifying question and is waiting on
# a human answer + re-dispatch. They hold no WIP slot but must not be
# re-claimed by intake either — the issue still carries agent:queued.
PARKED=$(jq '[.claims[] | select(.status == "spec-clarify-pending")]' "$QUEUE")
PARKED_COUNT=$(jq 'length' <<<"$PARKED")
SLOTS=$((WIP_CAP - ACTIVE_COUNT))
echo "WIP: $ACTIVE_COUNT/$WIP_CAP active claims — $SLOTS open slot(s); $PARKED_COUNT parked on clarification"

# Open agent:queued issues; the issues API also returns PRs, drop them.
CANDIDATES=$(gh api --paginate "repos/$TICKET_REPO/issues?labels=agent:queued&state=open&per_page=100" \
  --jq '.[] | select(has("pull_request") | not) | {number, title, labels: [.labels[].name]}' | jq -s '.')
echo "Candidates: $(jq 'length' <<<"$CANDIDATES") open agent:queued issue(s)"

refuse() { # <issue> <reason-markdown>
  gh api -X POST "repos/$TICKET_REPO/issues/$1/comments" -f body="$2" >/dev/null
  gh api -X DELETE "repos/$TICKET_REPO/issues/$1/labels/agent%3Aqueued" >/dev/null || true
  echo "REFUSED #$1"
}

# A repo is routable only if the human allowlist names it AND an expertise
# guard list exists for it. The guard file is what stops the coding agent
# writing to reserved paths, so a repo without one is not safe to target.
routable() { # <short-repo-name>
  jq -e --arg r "$1" '.repos[$r].routable == true' "$ALLOWLIST" >/dev/null 2>&1 &&
    [ -f "guards/$1.paths" ]
}

# Side effects deferred until the queue commit lands.
POST_CARDS=()         # "<issue>\t<impl_repo>\t<branch>"
POST_LABEL_DROPS=()   # "<issue>"
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

  # Routing. The "Repos involved" checklist in the ticket body is NOT the
  # signal: it is prose written for humans and it is wrong in both directions
  # (tickets check a repo then annotate "no changes"; tickets needing three
  # repos leave every box unchecked). Labels are explicit and machine-owned.
  targets=$(grep '^repo:' <<<"$labels" | sed 's/^repo://' | sort -u || true)
  if [ -z "$targets" ]; then
    refuse "$num" "This ticket has \`agent:queued\` but no \`repo:<name>\` label, so intake cannot tell which repository the work lands in. The \"Repos involved\" checklist in the body is not used for routing — it is prose, and it disagrees with itself often enough that parsing it would send work to the wrong repo. Removed \`agent:queued\`; add e.g. \`repo:example-app-sdk-js\` (one label per repo the change touches) and re-queue."
    continue
  fi
  bad=""
  for t in $targets; do routable "$t" || bad="$bad \`repo:$t\`"; done
  if [ -n "$bad" ]; then
    refuse "$num" "Unroutable target(s):$bad. A repo is routable only when it is listed in \`state/impl-repos.json\` *and* has a \`guards/<repo>.paths\` expertise list in agent-ops — the guard file is what keeps the agent out of reserved paths, so a repo without one is not safe to target. Removed \`agent:queued\`; add the repo to both files, then re-queue."
    continue
  fi

  ticket_claims=0
  for target in $targets; do
    impl_repo="<YOUR_ORG>/$target"

    if jq -e --argjson n "$num" --arg r "$impl_repo" 'any(.[]; .issue == $n and .impl_repo == $r)' <<<"$ACTIVE" >/dev/null; then
      echo "SKIP #$num -> $target: already claimed"
      continue
    fi
    if jq -e --argjson n "$num" --arg r "$impl_repo" 'any(.[]; .issue == $n and .impl_repo == $r)' <<<"$PARKED" >/dev/null; then
      echo "SKIP #$num -> $target: parked on a clarifying question — answer on the ticket, then re-dispatch spec-draft"
      continue
    fi
    # Orphan-branch check. A failed API call used to leave this test as
    # `[ "" -gt 0 ]` — a bash error under set -e that killed intake mid-loop
    #. Unknown = do not claim, say so, move on.
    if ! existing=$(GH_TOKEN="$IMPL_GH_TOKEN" gh api "repos/$impl_repo/git/matching-refs/heads/agent/$num-" --jq 'length' 2>/dev/null); then
      echo "::warning::SKIP #$num -> $target: could not list agent/$num-* refs on $impl_repo (API error) — not claiming"
      continue
    fi
    if [ "${existing:-0}" -gt 0 ]; then
      echo "::warning::SKIP #$num -> $target: agent/$num-* branch exists with no active claim — investigate before re-queuing"
      continue
    fi
    if [ "$CLAIMED" -ge "$SLOTS" ]; then
      echo "SKIP #$num -> $target: WIP cap reached"
      continue
    fi

    slug=$(tr '[:upper:]' '[:lower:]' <<<"$title" | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-40 | sed -E 's/-+$//')
    [ -n "$slug" ] || slug=ticket
    branch="agent/$num-$slug"
    class=$( (grep -m1 '^class:' <<<"$labels" || true) | sed 's/^class://')
    [ -n "$class" ] || class=unclassified

    claim=$(jq -n --argjson issue "$num" --arg repo "$TICKET_REPO" --arg impl "$impl_repo" \
      --arg title "$title" --arg class "$class" --arg at "$NOW" --arg run "$RUN_URL" --arg branch "$branch" \
      '{issue: $issue, repo: $repo, impl_repo: $impl, title: $title, mode: "claude-led",
        ticket_class: $class, claimed_at: $at, run_url: $run, branch: $branch, status: "claimed"}')
    # One row per (issue, impl_repo): a re-claim after abandon/merge replaces
    # the terminal row rather than appending beside it. update-claim.sh cannot
    # resolve a status across two rows for one key;
    # the abandonment itself stays on record in the status card's history
    # and in this file's history.
    jq --argjson c "$claim" --slurpfile t "$(dirname "$0")/../state/transitions.json" '
      ($t[0] | to_entries | map(select(.value | length == 0) | .key)) as $terminal
      | .claims |= (map(select(.status as $s
                               | (.issue == $c.issue and .impl_repo == $c.impl_repo
                                  and (($terminal | index($s)) != null)) | not))
                    + [$c])' "$QUEUE" > "$QUEUE.tmp" && mv "$QUEUE.tmp" "$QUEUE"

    POST_CARDS+=("$num"$'\t'"$impl_repo"$'\t'"$branch")
    echo "CLAIM $num $branch $target"
    CLAIMED=$((CLAIMED + 1))
    ticket_claims=$((ticket_claims + 1))
  done

  # Queuing is acceptance of the groomed body: drop the human-review label so
  # the grooming loop never touches a claimed ticket (groom:review / groom:redo
  # are the only two grooming states; see example-app-core label descriptions).
  # Once per ticket, not once per target — and only if the ticket actually
  # produced a claim, so a WIP-capped ticket keeps its review state. Deferred
  # until the commit below succeeds.
  if [ "$ticket_claims" -gt 0 ]; then
    POST_LABEL_DROPS+=("$num")
  fi
done < <(jq -c '.[]' <<<"$CANDIDATES")

if [ "$CLAIMED" -eq 0 ]; then
  echo "No new claims."
  exit 0
fi

# The commit is the claim. If it fails, nothing below runs and the tickets
# stay exactly as they were: no status card, no label change.
bash scripts/commit-state.sh "$QUEUE" "$BEFORE" "intake: claim $CLAIMED ticket(s)"

# One status card per (issue, impl_repo). A re-claim finds the card the
# previous lifecycle left and continues its history instead of adding a
# second comment. The script warns and exits 0 on any API error: the card is
# cosmetic, the queue commit above is the claim.
for entry in "${POST_CARDS[@]}"; do
  IFS=$'\t' read -r num impl_repo branch <<<"$entry"
  python3 "$(dirname "$0")/status-card.py" upsert --repo "$TICKET_REPO" --issue "$num" --impl-repo "$impl_repo" \
    --event claimed --status claimed --set "branch=$branch" --run-url "$RUN_URL" \
    --note "claimed by agent-ops — next: spec draft"
done
for num in "${POST_LABEL_DROPS[@]}"; do
  gh api -X DELETE "repos/$TICKET_REPO/issues/$num/labels/groom%3Areview" >/dev/null 2>&1 || true
done
