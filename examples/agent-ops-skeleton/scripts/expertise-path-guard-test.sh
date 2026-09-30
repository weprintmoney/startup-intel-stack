#!/usr/bin/env bash
# Self-test for expertise-path-guard.sh: builds a synthetic repo and asserts
# the guard fails on guarded paths (top-level, nested, deletions) and passes
# on unguarded changes. Run by expertise-path-guard.yml on agent-ops PRs.
set -euo pipefail

GUARD="$(cd "$(dirname "$0")" && pwd)/expertise-path-guard.sh"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"   # resolved before the cd below
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/test.paths" <<'EOF'
# comment line

src/encrypted_index*
src/cpu/**
src/utils/api_key.*
EOF

git -c init.defaultBranch=main init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email test@example.com
git config user.name test
mkdir -p src/cpu src/utils docs
echo base > README.md
echo base > src/utils/api_key.cpp
git add -A && git commit -qm base

fail() { echo "SELF-TEST FAIL: $1" >&2; exit 1; }

# 1. Guarded top-level file -> must fail
git checkout -qb t1
echo x > src/encrypted_index.cpp
git add -A && git commit -qm t1
bash "$GUARD" "$TMP/test.paths" main HEAD && fail "passed change to src/encrypted_index.cpp"

# 2. Nested file under a ** glob -> must fail
git checkout -q main && git checkout -qb t2
mkdir -p src/cpu/deep && echo x > src/cpu/deep/kernel.cpp
git add -A && git commit -qm t2
bash "$GUARD" "$TMP/test.paths" main HEAD && fail "passed change to src/cpu/deep/kernel.cpp"

# 3. Deleting a guarded file -> must fail
git checkout -q main && git checkout -qb t3
git rm -q src/utils/api_key.cpp && git commit -qm t3
bash "$GUARD" "$TMP/test.paths" main HEAD && fail "passed deletion of src/utils/api_key.cpp"

# 4. Unguarded change -> must pass
git checkout -q main && git checkout -qb t4
echo x > docs/notes.md && echo y > src/utils/math.hpp
git add -A && git commit -qm t4
bash "$GUARD" "$TMP/test.paths" main HEAD || fail "failed a clean change"

# 5. Missing guards file -> must fail (fail closed)
bash "$GUARD" "$TMP/nonexistent.paths" main HEAD 2>/dev/null && fail "passed with missing guards file"

# 6. Real per-repo guard lists. These run the shipped guards/<repo>.paths
# against paths taken from each repo's actual tree, so a typo'd glob fails
# here instead of silently guarding nothing in production. Split by intent:
# the "allow" set is the work the pilot has to be able to do; the "block"
# set is the code areas, the CI checks that grade the agent, and the security
# tests it must never be able to soften.
git checkout -q main && git checkout -qb t6
mkdir -p sdkcase && echo base > sdkcase/base.txt
git add -A && git commit -qm t6-base

sdk_case() { # <repo> allow|block <path>
  local repo=$1 want=$2 path=$3
  local guards="$REPO_ROOT/guards/$repo.paths"
  [ -f "$guards" ] || fail "no guards/$repo.paths"
  git checkout -q t6 && git checkout -q -B t6-case
  mkdir -p "$(dirname "$path")" && echo x > "$path"
  git add -A && git commit -qm case
  if bash "$GUARD" "$guards" t6 HEAD >/dev/null 2>&1; then
    [ "$want" = allow ] || fail "$repo: '$path' should be BLOCKED but passed"
  else
    [ "$want" = block ] || fail "$repo: '$path' should be ALLOWED but was blocked"
  fi
  git checkout -q t6 && git branch -qD t6-case
}

# Core: reserved (billing/auth/session/payments/migrations and CI config).
sdk_case example-app-core block "src/billing/invoice.py"
sdk_case example-app-core block "src/auth/login.py"
sdk_case example-app-core block "src/session/store.py"
sdk_case example-app-core block "src/payments/charge.py"
sdk_case example-app-core block "migrations/0001_init.sql"
sdk_case example-app-core block ".github/workflows/ci.yml"
# Core: must stay implementable.
sdk_case example-app-core allow "src/client.py"
sdk_case example-app-core allow "src/utils/math_utils.py"
sdk_case example-app-core allow "docs/notes.md"
sdk_case example-app-core allow "README.md"

# Service: reserved.
sdk_case example-app-service block "src/api/public/routes.py"
sdk_case example-app-service block "src/webhooks/handler.py"
sdk_case example-app-service block "src/data-access/repo.py"
sdk_case example-app-service block "config/production/settings.yaml"
sdk_case example-app-service block ".github/workflows/test.yml"
sdk_case example-app-service block ".github/dependabot.yml"
# Service: must stay implementable.
sdk_case example-app-service allow "src/api/internal/health.py"
sdk_case example-app-service allow "src/core/config.py"
sdk_case example-app-service allow "README.md"

# agent-ops itself: the agent may add sandbox code but never touch the gates
# that grade it or the state it runs on.
sdk_case agent-ops allow "scripts/sandbox/parse_semver.py"
sdk_case agent-ops allow "scripts/sandbox/parse_semver_test.py"
sdk_case agent-ops allow "docs/notes.md"
sdk_case agent-ops block ".github/workflows/code-judge.yml"
sdk_case agent-ops block "guards/example-app-core.paths"
sdk_case agent-ops block "state/queue.json"
sdk_case agent-ops block "agents/code-judge/CLAUDE.md"
sdk_case agent-ops block "scripts/round-history.py"
sdk_case agent-ops block "CLAUDE.md"

# 9. main advances past a guarded path after the branch forked: a two-dot
# `git diff main..t9` is a raw tree comparison with no ancestry, so it would
# read main's new commit as part of t9's diff too and fail a branch that
# never touched it. Regression test for a live incident this fixed (a
# sandbox-verification PR, forked before unrelated merges landed on
# guarded paths).
git checkout -q main && git checkout -qb t9
mkdir -p docs && echo x > docs/other.md && git add -A && git commit -qm t9
git checkout -q main
mkdir -p src/cpu && echo y > src/cpu/new_kernel.cpp && git add -A && git commit -qm "unrelated main commit touching a guarded path"
git checkout -q t9
bash "$GUARD" "$TMP/test.paths" main HEAD || fail "a branch whose own diff is clean was failed by main's post-fork guarded change"

echo "expertise-path-guard self-test: all synthetic and per-repo guard cases passed"
