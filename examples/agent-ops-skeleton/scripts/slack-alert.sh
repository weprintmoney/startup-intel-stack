#!/usr/bin/env bash
# Post an ops/failure alert to the agent-ops Slack channel (never #core-team).
# Degrades to log-only when SLACK_BOT_TOKEN is unset (pre-setup, issue #1).
# Usage: slack-alert.sh <text>
set -euo pipefail

TEXT="${1:?usage: slack-alert.sh <text>}"
CHANNEL="${SLACK_OPS_CHANNEL_ID}"

echo "$TEXT"
if [ -z "${SLACK_BOT_TOKEN:-}" ]; then
  echo "(SLACK_BOT_TOKEN not set — alert logged only)"
  exit 0
fi

curl -sS -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg c "$CHANNEL" --arg t "$TEXT" '{channel: $c, text: $t}')" >/dev/null \
  || echo "::warning::Slack alert failed to send"
