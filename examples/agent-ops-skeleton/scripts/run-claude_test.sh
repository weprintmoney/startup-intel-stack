#!/usr/bin/env bash
# Tests run-claude.sh's prompt handling without calling the API: a `claude`
# shim on PATH records its argv and writes a minimal stream-json result.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
cat > "$TMP/bin/claude" <<'SHIM'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$CLAUDE_SHIM_ARGS"
echo '{"type":"result","subtype":"success","result":"RESULT: OK","total_cost_usd":0}'
SHIM
chmod +x "$TMP/bin/claude"
export PATH="$TMP/bin:$PATH" HOME="$TMP/home" CLAUDE_SHIM_ARGS="$TMP/args"
mkdir -p "$HOME"
FAILS=0
fail() { echo "FAIL: $1" >&2; FAILS=$((FAILS+1)); }

# 1. persona + task block -> persona in --append-system-prompt-file, task as -p
PROMPT=$'# Judge persona\n\nYou judge diffs.\n\nTask: judge PR #1.\nInputs at: /tmp/review-input\nWrite output to: /tmp/review-output/verdict.json\nEnd with exactly one RESULT: line.'
bash "$HERE/run-claude.sh" "$TMP/a.jsonl" "$PROMPT" --model m --max-turns 3 >/dev/null
grep -qx -- "--append-system-prompt-file" "$TMP/args" || fail "no --append-system-prompt-file flag"
PF=$(grep -A1 -x -- "--append-system-prompt-file" "$TMP/args" | tail -1)
[ "$(cat "$PF")" = $'# Judge persona\n\nYou judge diffs.' ] || fail "persona file content wrong: $(cat "$PF")"
P=$(sed -n '2p' "$TMP/args"); [ "${P%%$'\n'*}" = "Task: judge PR #1." ] || fail "user prompt should start at Task:, got: ${P:0:40}"
grep -qx -- "--max-turns" "$TMP/args" || fail "caller flags dropped"
echo "ok:   persona split into system prompt, task stays in -p"

# 2. Inputs at: as the first task line (claim-verifier shape)
PROMPT=$'persona line\n\nInputs at: /tmp/claim-verify\nWrite verdict to: /tmp/claim-verify/verdict.json'
bash "$HERE/run-claude.sh" "$TMP/b.jsonl" "$PROMPT" >/dev/null
[ "$(sed -n '2p' "$TMP/args")" = "Inputs at: /tmp/claim-verify" ] || fail "Inputs at: split failed"
echo "ok:   Inputs at: recognised as the task start"

# 3. no task block -> prompt passed through unchanged, no system-prompt flag
PROMPT=$'just a prompt\nwith two lines'
bash "$HERE/run-claude.sh" "$TMP/c.jsonl" "$PROMPT" >/dev/null
grep -qx -- "--append-system-prompt-file" "$TMP/args" && fail "flag added without a task block"
[ "$(sed -n '2p' "$TMP/args")" = "just a prompt" ] || fail "prompt altered"
echo "ok:   prompt without a task block is untouched"

# 4. opt-out
PROMPT=$'persona\n\nTask: x'
RUN_CLAUDE_INLINE_PERSONA=1 bash "$HERE/run-claude.sh" "$TMP/d.jsonl" "$PROMPT" >/dev/null
grep -qx -- "--append-system-prompt-file" "$TMP/args" && fail "opt-out ignored"
echo "ok:   RUN_CLAUDE_INLINE_PERSONA=1 keeps the persona inline"

# 5. a Task: line inside the persona body (not after a blank line) is not a split point
PROMPT=$'persona\nTask: this is prose in the persona\nmore persona\n\nTask: real task'
bash "$HERE/run-claude.sh" "$TMP/e.jsonl" "$PROMPT" >/dev/null
[ "$(sed -n '2p' "$TMP/args")" = "Task: real task" ] || fail "split at the wrong Task: line"
echo "ok:   only a Task: after a blank line splits"

# 6. settings.json gets includeCoAuthoredBy=false
grep -q '"includeCoAuthoredBy": *false' "$HOME/.claude/settings.json" || fail "settings.json not written"
echo "ok:   attribution disabled in settings.json"

if [ "$FAILS" -eq 0 ]; then
  echo "all run-claude tests passed"
else
  echo "$FAILS failure(s)"
  exit 1
fi
