#!/usr/bin/env bash
# Unit tests for scripts/update-claim.sh's transition enforcement
# (state/transitions.json). Run by schema-validate.yml.
#
# Exercises the real script end-to-end, including commit-state.sh, against
# a throwaway repo with its own local bare "origin" — no network, no
# touching this checkout.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
FAILS=0

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

ORIGIN="$TMP/origin.git"
git init --bare -q "$ORIGIN"

REPO="$TMP/repo"
git clone -q "$ORIGIN" "$REPO" 2>/dev/null
cd "$REPO"
git config user.name test
git config user.email test@example.com
git checkout -qB main

mkdir -p state scripts
cp "$ROOT/state/transitions.json" state/transitions.json
cp "$HERE/update-claim.sh" scripts/update-claim.sh
cp "$HERE/commit-state.sh" scripts/commit-state.sh
cp "$HERE/state-retry.sh" scripts/state-retry.sh
cp "$HERE/slack-alert.sh" scripts/slack-alert.sh
chmod +x scripts/*.sh
export STATE_RETRY_SLEEP=0
unset SLACK_BOT_TOKEN

cat > state/queue.json <<'EOF'
{
  "wip_cap": 2,
  "claims": [
    {"issue": 1, "repo": "example-org/example-app-core", "impl_repo": "example-org/example-app-core", "mode": "claude-led", "ticket_class": "docs", "claimed_at": "2026-01-01T00:00:00Z", "run_url": "https://x", "branch": "agent/1-x", "status": "pr-open"},
    {"issue": 2, "repo": "example-org/example-app-core", "impl_repo": "example-org/example-app-core", "mode": "claude-led", "ticket_class": "docs", "claimed_at": "2026-01-01T00:00:00Z", "run_url": "https://x", "branch": "agent/2-x", "status": "spec-clarify-pending"},
    {"issue": 3, "repo": "example-org/example-app-core", "impl_repo": "example-org/example-app-core", "mode": "claude-led", "ticket_class": "docs", "claimed_at": "2026-01-01T00:00:00Z", "run_url": "https://x", "branch": "agent/3-x", "status": "spec-pending"},
    {"issue": 4, "repo": "example-org/example-app-core", "impl_repo": "example-org/example-app-core", "mode": "claude-led", "ticket_class": "docs", "claimed_at": "2026-01-01T00:00:00Z", "run_url": "https://x", "branch": "agent/4-x", "status": "spec-approved"},
    {"issue": 5, "repo": "example-org/example-app-core", "impl_repo": "example-org/example-app-core", "mode": "claude-led", "ticket_class": "docs", "claimed_at": "2026-01-01T00:00:00Z", "run_url": "https://x", "branch": "agent/5-x", "status": "abandoned", "abandoned_reason": "first attempt", "closed_at": "2026-01-02T00:00:00Z"},
    {"issue": 5, "repo": "example-org/example-app-core", "impl_repo": "example-org/example-app-core", "mode": "claude-led", "ticket_class": "docs", "claimed_at": "2026-01-03T00:00:00Z", "run_url": "https://x", "branch": "agent/5-x", "status": "claimed"}
  ]
}
EOF
git add -A
git commit -qm init
git push -qu origin main

run() { IMPL_REPO=example-org/example-app-core bash scripts/update-claim.sh "$@"; }

check_rejected() { # <desc> <issue> <status>
  local desc="$1" issue="$2" status="$3" rc=0 out
  out=$(run "$issue" "$status" 2>&1) || rc=$?
  if [ "$rc" -eq 1 ] && grep -q "illegal transition" <<<"$out"; then
    echo "ok:   $desc"
  else
    echo "FAIL: $desc (exit=$rc): $out"; FAILS=$((FAILS+1))
  fi
}

check_accepted() { # <desc> <issue> <status> <expected-status-after>
  local desc="$1" issue="$2" status="$3" expect="$4" rc=0 out
  out=$(run "$issue" "$status" 2>&1) || rc=$?
  local actual; actual=$(jq -r --argjson n "$issue" '.claims[] | select(.issue == $n) | .status' state/queue.json)
  if [ "$rc" -eq 0 ] && [ "$actual" = "$expect" ]; then
    echo "ok:   $desc"
  else
    echo "FAIL: $desc (exit=$rc, status=$actual): $out"; FAILS=$((FAILS+1))
  fi
}

# The plan's own acceptance example: pr-open -> claimed must be rejected.
check_rejected "pr-open -> claimed rejected"                  1 claimed
check_rejected "spec-pending -> implementing rejected (skips spec-approved)" 3 implementing
check_rejected "spec-pending -> pr-open rejected"              3 pr-open

check_accepted "pr-open -> merged accepted"                    1 merged merged
check_accepted "spec-clarify-pending -> spec-clarify-pending self-loop accepted" 2 spec-clarify-pending spec-clarify-pending
check_accepted "spec-pending -> spec-approved accepted"        3 spec-approved spec-approved
check_accepted "spec-approved -> implementing accepted"        3 implementing implementing
# The 2026-09-16 fan-out incident: a cancelled
# implement.yml run had already transitioned the claim to "implementing";
# the re-dispatch's own "Mark claim implementing" step then failed with
# "illegal transition 'implementing' -> 'implementing'" and the claim was
# abandoned even though nothing had actually been attempted. A resumed or
# re-dispatched run must be able to re-affirm the status it is already in.
check_accepted "implementing -> implementing self-loop accepted (resume after interrupted run)" 3 implementing implementing
# A claim whose spec merged but that will never be dispatched (ticket closed
# or superseded by hand-written work) previously had no path off
# spec-approved and held a WIP slot forever.
check_accepted "spec-approved -> abandoned accepted (ticket closed before implementation)" 4 abandoned abandoned

# Two rows for one (issue, impl_repo): a stale terminal row beside the live
# one. The
# transition must resolve against the live row and leave the terminal row
# untouched, instead of newline-joining both statuses into a FROM that
# matches nothing in transitions.json.
out=$(run 5 spec-pending '{"spec_path":"x.md"}' 2>&1) || {
  echo "FAIL: dup rows: claimed -> spec-pending should succeed: $out"; FAILS=$((FAILS+1))
}
got=$(jq -r '[.claims[] | select(.issue == 5) | .status] | join(",")' state/queue.json)
if [ "$got" = "abandoned,spec-pending" ]; then echo "ok:   dup rows: live row transitioned, terminal row untouched"; else
  echo "FAIL: dup rows: expected 'abandoned,spec-pending', got '$got'"; FAILS=$((FAILS+1))
fi
patched=$(jq -r '[.claims[] | select(.issue == 5) | .spec_path // "-"] | join(",")' state/queue.json)
if [ "$patched" = "-,x.md" ]; then echo "ok:   dup rows: patch applied to the live row only"; else
  echo "FAIL: dup rows: patch landed on the wrong row(s): $patched"; FAILS=$((FAILS+1))
fi

# "-" (patch-only) bypasses transition enforcement entirely, regardless of
# current status.
out=$(IMPL_REPO=example-org/example-app-core bash scripts/update-claim.sh 1 - '{"merge_sha":"abc1234"}' 2>&1) || {
  echo "FAIL: '-' patch-only call should succeed: $out"; FAILS=$((FAILS+1))
}
sha=$(jq -r '.claims[] | select(.issue == 1) | .merge_sha' state/queue.json)
if [ "$sha" = "abc1234" ]; then echo "ok:   '-' patch-only call bypasses enforcement"; else
  echo "FAIL: '-' patch-only call did not apply patch"; FAILS=$((FAILS+1))
fi

# pr-review-reap.yml's idempotency field: a patch-only
# write, same as merge_sha above.
out=$(IMPL_REPO=example-org/example-app-core bash scripts/update-claim.sh 1 - '{"last_review_dispatched":"123456789"}' 2>&1) || {
  echo "FAIL: last_review_dispatched patch should succeed: $out"; FAILS=$((FAILS+1))
}
seen=$(jq -r '.claims[] | select(.issue == 1) | .last_review_dispatched' state/queue.json)
if [ "$seen" = "123456789" ]; then echo "ok:   last_review_dispatched patch applied"; else
  echo "FAIL: last_review_dispatched patch did not apply"; FAILS=$((FAILS+1))
fi

# --- Lost queue.json races ------------------------------
# A second clone plays the concurrent writer: it lands a queue.json change
# on origin after this checkout last pulled, so this checkout's push is
# rejected and the rebase of two jq rewrites of one document conflicts.
OTHER="$TMP/other"
git clone -q "$ORIGIN" "$OTHER" 2>/dev/null
# Pin the branch: a runner whose init.defaultBranch is master clones the
# bare origin onto an unborn master.
(cd "$OTHER" && git checkout -qB main origin/main && git config user.name other && git config user.email other@example.com)
other_writes() { # <issue> <status> — the concurrent writer's transition
  (cd "$OTHER" && git pull -q --rebase origin main && IMPL_REPO=example-org/example-app-core bash scripts/update-claim.sh "$1" "$2" >/dev/null 2>&1)
}
status_on_origin() { # <issue> — last row's status as origin/main holds it
  git fetch -q origin main
  git show origin/main:state/queue.json | jq -r --argjson n "$1" '[.claims[] | select(.issue == $n)][-1].status'
}

# Different claims: the replay of 2026-09-23. This checkout
# goes stale holding the last claim (7); the other writer is intake,
# appending claim 8 right after it — adjacent hunks, so the rebase
# conflicts exactly as it did in production. Our transition must still
# land, and intake's claim must survive.
other_claims() { # <issue> — append a fresh `claimed` row from the other clone
  (cd "$OTHER" && git pull -q --rebase origin main \
    && jq --argjson n "$1" '.claims += [{"issue":$n,"repo":"example-org/example-app-core","impl_repo":"example-org/example-app-core","mode":"claude-led","ticket_class":"docs","claimed_at":"2026-01-04T00:00:00Z","run_url":"https://x","branch":"agent/\($n)-x","status":"claimed"}]' state/queue.json > q \
    && mv q state/queue.json && git commit -qam "intake: claim #$1" && git push -q origin main)
}
other_claims 6; other_claims 7
git pull -q --rebase origin main
other_claims 8
rc=0; out=$(run 7 spec-pending '{"spec_path":"7.md"}' 2>&1) || rc=$?
s7=$(status_on_origin 7); s8=$(status_on_origin 8)
if [ "$rc" -eq 0 ] && [ "$s7" = "spec-pending" ] && [ "$s8" = "claimed" ] && grep -q "lost a race" <<<"$out"; then
  echo "ok:   replay 2026-09-23: lost race to intake, re-applied, both writes landed"
else
  echo "FAIL: replay 2026-09-23 (exit=$rc, #7=$s7, #8=$s8): $out"; FAILS=$((FAILS+1))
fi

# Same claim: we hold 6 at spec-pending and move it to spec-approved; the
# other writer abandons 6 first. After the resync the transition is
# abandoned -> spec-approved, which is illegal: exit 1 (not retried) and
# origin keeps the winner.
git pull -q --rebase origin main
other_writes 6 abandoned
rc=0; out=$(run 6 spec-approved 2>&1) || rc=$?
s6=$(status_on_origin 6)
if [ "$rc" -eq 1 ] && grep -q "illegal transition 'abandoned' -> 'spec-approved'" <<<"$out" && [ "$s6" = "abandoned" ]; then
  echo "ok:   lost race on the same claim: fresh-state re-check rejects, winner kept"
else
  echo "FAIL: lost race on the same claim (exit=$rc, #6=$s6): $out"; FAILS=$((FAILS+1))
fi

# Exhausted retries: a writer that always loses exits 2 and alerts.
rc=0; out=$(STATE_RETRY_ATTEMPTS=3 bash scripts/state-retry.sh state/queue.json bash -c 'exit 2' 2>&1) || rc=$?
if [ "$rc" -eq 2 ] && grep -q "dropped after 3 attempts" <<<"$out"; then
  echo "ok:   exhausted retries exit 2 and alert"
else
  echo "FAIL: exhausted retries (exit=$rc): $out"; FAILS=$((FAILS+1))
fi

# Non-race failures pass straight through, un-retried.
rc=0; out=$(bash scripts/state-retry.sh state/queue.json bash -c 'echo once; exit 1' 2>&1) || rc=$?
if [ "$rc" -eq 1 ] && [ "$(grep -c once <<<"$out")" -eq 1 ]; then
  echo "ok:   non-race failure returned once, not retried"
else
  echo "FAIL: non-race failure (exit=$rc): $out"; FAILS=$((FAILS+1))
fi

# Every claim was actually committed and pushed by commit-state.sh.
# (grep -q on a live `git log | ...` pipe can SIGPIPE the writer under
# pipefail once grep finds its match and exits early -- capture first.)
LOG=$(git log --oneline)
if grep -q "claim #1" <<<"$LOG"; then
  echo "ok:   commit-state.sh committed the transitions"
else
  echo "FAIL: expected commits from update-claim.sh not found"; FAILS=$((FAILS+1))
fi

if [ "$FAILS" -ne 0 ]; then echo "$FAILS test(s) failed"; exit 1; fi
echo "all update-claim transition tests passed"
