#!/usr/bin/env bash
# Unit tests for scripts/result-line.sh. Run by schema-validate.yml.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RL="$HERE/result-line.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
FAILS=0

stream() { # <name> <final-text>  -> writes a minimal stream-json file
  jq -nc --arg t "$2" '{type:"system"}, {type:"assistant"}, {type:"result", subtype:"success", result:$t, total_cost_usd:0.5}' > "$TMP/$1.jsonl"
}
check() { # <desc> <expected-result> <expected-detail> <cmd...>
  local desc="$1" er="$2" ed="$3"; shift 3
  local out; out=$("$@")
  local r d
  r=$(sed -n 's/^result=//p' <<<"$out"); d=$(sed -n 's/^result_detail=//p' <<<"$out")
  if [ "$r" != "$er" ] || [ "$d" != "$ed" ]; then
    echo "FAIL: $desc"; echo "   want result='$er' detail='$ed'"; echo "   got  result='$r' detail='$d'"; FAILS=$((FAILS+1))
  else
    echo "ok:   $desc"
  fi
}

stream plain      $'Drafted the spec.\nSPEC_PATH: 07-eng/specs/features/1-x.md\nRESULT: SPEC_PR https://github.com/o/r/pull/591'
check "plain SPEC_PR keeps its underscore"      SPEC_PR "https://github.com/o/r/pull/591" bash "$RL" "$TMP/plain.jsonl"

stream ticks      $'Done.\n`RESULT: FAST_PATH`'
check "backticked token"                        FAST_PATH "" bash "$RL" "$TMP/ticks.jsonl"

stream bold       $'**RESULT: DEPENDENCY_BLOCKED** example-app-core#2134 owner:eng-lead-handle'
check "bold label + detail with owner trailer"  DEPENDENCY_BLOCKED "example-app-core#2134 owner:eng-lead-handle" bash "$RL" "$TMP/bold.jsonl"

stream italic     $'_RESULT: CLARIFY_NEEDED which repo owns the retry policy?_'
check "underscore-italic wrapper stripped at edges only" CLARIFY_NEEDED "which repo owns the retry policy?" bash "$RL" "$TMP/italic.jsonl"

stream bullet     $'- RESULT: GROOMING_BLOCKER body contradicts cited ADR'
check "list-bullet prefix tolerated"            GROOMING_BLOCKER "body contradicts cited ADR" bash "$RL" "$TMP/bullet.jsonl"

stream quote      $'> RESULT: UNFIT touches guards'
check "blockquote prefix tolerated"             UNFIT "touches guards" bash "$RL" "$TMP/quote.jsonl"

stream last       $'I will end with RESULT: PLANNED once done.\nRESULT: BLOCKED plan-missing'
check "last matching line wins"                 BLOCKED "plan-missing" bash "$RL" "$TMP/last.jsonl"

stream prose      $'The RESULT: line is below.\nRESULT: IMPLEMENTED.'
check "trailing punctuation stripped from token" IMPLEMENTED "" bash "$RL" "$TMP/prose.jsonl"

stream judge      $'RESULT: VERDICT pass 100'
check "judge verdict token + numeric detail"    VERDICT "pass 100" bash "$RL" "$TMP/judge.jsonl"

stream nospace    $'RESULT:REVISED 3 fixed'
check "no space after label"                    REVISED "3 fixed" bash "$RL" "$TMP/nospace.jsonl"

stream none       $'I could not finish.'
check "no RESULT line -> empty"                 "" "" bash "$RL" "$TMP/none.jsonl"

stream retry      $'RESULT: BLOCKED retry-fingerprint a1b2c3d4 Bash'
check "hyphenated detail preserved"             BLOCKED "retry-fingerprint a1b2c3d4 Bash" bash "$RL" "$TMP/retry.jsonl"

stream handoff    $'RESULT: BLOCKED github-app-missing-workflows-permission .github/workflows/package-test.yml'
check "workflows hand-off detail"               BLOCKED "github-app-missing-workflows-permission .github/workflows/package-test.yml" bash "$RL" "$TMP/handoff.jsonl"

printf 'VERDICT: request-changes\n\n## Spec conformance\nVERDICT: approve was considered.\n' > "$TMP/review.md"
check "--text --first VERDICT takes line one"   request-changes "" bash "$RL" --text --first "$TMP/review.md" VERDICT

printf '**VERDICT: approve**\nfindings...\n' > "$TMP/review2.md"
check "--text bold VERDICT"                     approve "" bash "$RL" --text --first "$TMP/review2.md" VERDICT

: > "$TMP/empty.jsonl"
check "empty stream file -> empty"              "" "" bash "$RL" "$TMP/empty.jsonl"

check "missing file -> empty, exit 0"           "" "" bash "$RL" "$TMP/does-not-exist.jsonl"

stream long "RESULT: BLOCKED $(head -c 400 /dev/zero | tr '\0' x)"
LONG=$(bash "$RL" "$TMP/long.jsonl" | sed -n 's/^result_detail=//p' | wc -c | tr -d ' ')
if [ "$LONG" -le 301 ]; then echo "ok:   detail capped at 300 chars"; else echo "FAIL: detail not capped ($LONG)"; FAILS=$((FAILS+1)); fi

if [ "$FAILS" -ne 0 ]; then echo "$FAILS test(s) failed"; exit 1; fi
echo "all result-line tests passed"
