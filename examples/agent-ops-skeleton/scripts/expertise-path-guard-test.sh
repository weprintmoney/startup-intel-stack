#!/usr/bin/env bash
# Self-test for expertise-path-guard.sh: builds a synthetic repo and asserts
# the guard fails on guarded paths (top-level, nested, deletions) and passes
# on unguarded changes. Run by expertise-path-guard.yml on agent-ops PRs.
set -euo pipefail

GUARD="$(cd "$(dirname "$0")" && pwd)/expertise-path-guard.sh"
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

echo "expertise-path-guard self-test: all 5 cases passed"
