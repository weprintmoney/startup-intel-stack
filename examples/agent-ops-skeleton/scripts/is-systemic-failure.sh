#!/usr/bin/env bash
# Detect whether a Claude Code stream transcript shows a systemic
# (infrastructure-class) failure rather than an isolated per-ticket
# failure. Used by workflow alert-on-failure steps to suppress the noisy
# per-issue Slack when 30 spec-drafts all fail for the same underlying
# reason (tier limit hit, credit balance, key auth, provider overload).
#
# Usage: is-systemic-failure.sh <path-to-stream.jsonl>
# Prints:  a short reason (e.g. "tier-limit synthetic response") on stdout
#          if a systemic signature is found. Silent otherwise.
# Exit:    0 = systemic (suppress per-issue Slack)
#          1 = not systemic OR transcript missing (post per-issue Slack)
#
# Add new signatures here as we learn them. Keep patterns anchored enough
# that a legitimately-produced spec containing the words "credit balance"
# in prose is not misclassified.
set -euo pipefail

TRANSCRIPT="${1:?usage: is-systemic-failure.sh <stream.jsonl>}"

# Missing transcript means the failure happened before Claude Code even
# started (checkout error, secret missing) — that IS an isolated failure
# from an alerting standpoint. Post normally.
if [ ! -f "$TRANSCRIPT" ] || [ ! -s "$TRANSCRIPT" ]; then
  exit 1
fi

# 1. Anthropic tier-limit / concurrency rejection.
#    Shape: a "result" record with model "<synthetic>" and duration_api_ms 0.
if grep -qE '"model"[[:space:]]*:[[:space:]]*"<synthetic>"' "$TRANSCRIPT"; then
  echo "tier-limit synthetic response (Anthropic concurrency cap)"
  exit 0
fi

# 2. Credit balance exhausted.
if grep -qiE 'credit balance is too low|insufficient[_ ]credits?' "$TRANSCRIPT"; then
  echo "credit balance too low (Anthropic account funds)"
  exit 0
fi

# 3. Authentication failure (wrong key, revoked, malformed).
if grep -qiE '"type"[[:space:]]*:[[:space:]]*"authentication_error"|invalid_api_key|invalid[_ ]auth' "$TRANSCRIPT"; then
  echo "authentication_error (Anthropic API key)"
  exit 0
fi

# 4. Provider overload (5xx from Anthropic).
if grep -qiE '"type"[[:space:]]*:[[:space:]]*"overloaded_error"|"status"[[:space:]]*:[[:space:]]*529' "$TRANSCRIPT"; then
  echo "anthropic overloaded (transient provider capacity)"
  exit 0
fi

# 5. Rate-limit distinct from tier-limit (per-minute token/request cap).
if grep -qiE '"type"[[:space:]]*:[[:space:]]*"rate_limit_error"' "$TRANSCRIPT"; then
  echo "rate_limit_error (Anthropic per-minute cap)"
  exit 0
fi

exit 1
