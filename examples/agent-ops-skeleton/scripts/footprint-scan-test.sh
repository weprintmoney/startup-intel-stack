#!/usr/bin/env bash
# Self-test for footprint-scan.sh: builds a synthetic repo and asserts the
# scanner fails on each footprint class (identity, trailer, config file,
# attribution string in the diff) and passes a clean range. Run by
# footprint-scan.yml on this repo's own PRs — scanning agent-ops' own PR range
# with production rules can never pass (this repo IS CLAUDE.md files), so the
# self-test is what proves the scanner works, same shape as
# expertise-path-guard-test.sh.
set -euo pipefail

SCAN="$(cd "$(dirname "$0")" && pwd)/footprint-scan.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

git -c init.defaultBranch=main init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email bot@example.com
git config user.name "example-app-bot[bot]"
git config commit.gpgsign false
echo base > README.md
mkdir -p src && echo 'def f(): return 1' > src/a.py
git add -A && git commit -qm base

fail() { echo "SELF-TEST FAIL: $1" >&2; exit 1; }
expect_fail() { # <desc>
  if bash "$SCAN" main HEAD >/dev/null 2>&1; then fail "passed but should have failed: $1"; fi
  echo "ok:   catches $1"
}
expect_pass() {
  bash "$SCAN" main HEAD >/dev/null 2>&1 || fail "failed but should have passed: $1"
  echo "ok:   passes $1"
}
reset() {
  if git checkout -q main; then
    git branch -qD t 2>/dev/null || true
  fi
  git checkout -qb t
}

# 1. Clean range passes
reset; echo 'def f(): return 2' > src/a.py; git add -A && git commit -qm "tighten f"
expect_pass "a clean bot-authored commit"

# 2. Author identity
reset; echo x > src/b.py; git add -A
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -qm "add b"
expect_fail "a Claude/Anthropic author identity"

# 3. Committer identity (author clean)
reset; echo x > src/b.py; git add -A
GIT_COMMITTER_NAME="Anthropic Bot" GIT_COMMITTER_EMAIL="bot@anthropic.com" git commit -qm "add b"
expect_fail "a Claude/Anthropic committer identity"

# 4. Co-authored-by trailer
reset; echo x > src/b.py; git add -A
git commit -qm $'add b\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>'
expect_fail "a Co-Authored-By Claude trailer"

# 5. "Generated with" marker + URL in the message
reset; echo x > src/b.py; git add -A
git commit -qm $'add b\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)'
expect_fail "a Generated-with Claude Code line"

# 6. Config files: CLAUDE.md at root, nested, .claude/ dir, .claude.json
reset; echo persona > CLAUDE.md; git add -A && git commit -qm "add persona"
expect_fail "a root CLAUDE.md"
reset; mkdir -p pkg && echo persona > pkg/CLAUDE.md; git add -A && git commit -qm "add persona"
expect_fail "a nested CLAUDE.md"
reset; mkdir -p .claude && echo '{}' > .claude/settings.json; git add -A && git commit -qm "add settings"
expect_fail "a .claude/ directory"
reset; echo '{}' > .claude.json; git add -A && git commit -qm "add cfg"
expect_fail "a .claude.json"

# 7. Attribution string added inside a file
reset; printf '# Generated with Claude Code\ndef g(): pass\n' > src/c.py; git add -A && git commit -qm "add c"
expect_fail "an attribution string added in the diff"

# 8. A commit message that merely mentions the words (no attribution shape) is not a footprint
reset; echo x > src/b.py; git add -A
git commit -qm "harden the client against anthropic-style header drift"
expect_pass "prose that mentions the vendor without an attribution marker"

# 9. main advances with its own footprint-bearing commit after the branch
# forked: a two-dot `git diff main..t` is a raw tree comparison and would
# read main's new commit as part of t's diff too, failing a branch that never
# touched it. Regression test for the live incident this fixed
# (expertise-path-guard.sh had the sibling bug).
reset; echo x > src/clean.py; git add -A && git commit -qm "clean, unrelated change"
git checkout -q main
printf '# Generated with Claude Code\n' >> README.md; git add -A && git commit -qm "unrelated main commit with a footprint"
git checkout -q t
expect_pass "a branch whose diff is clean even though main gained a footprint after the fork"

echo "footprint-scan self-test: all cases passed"
