#!/bin/bash
set -euo pipefail

yt-dlp --update-to nightly || true

if [[ "${TELEGRAM_LOCAL_MODE:-false}" == "true" ]]; then
  if [[ -z "${TELEGRAM_API_ID:-}" || -z "${TELEGRAM_API_HASH:-}" ]]; then
    echo "TELEGRAM_API_ID and TELEGRAM_API_HASH are required when TELEGRAM_LOCAL_MODE=true"
    exit 1
  fi

  export TELEGRAM_API_BASE_URL="${TELEGRAM_API_BASE_URL:-http://127.0.0.1:8081/bot}"
  export TELEGRAM_API_FILE_BASE_URL="${TELEGRAM_API_FILE_BASE_URL:-http://127.0.0.1:8081/file/bot}"

  mkdir -p /var/lib/telegram-bot-api /tmp/telegram-bot-api

  /usr/local/bin/telegram-bot-api \
    --api-id="${TELEGRAM_API_ID}" \
    --api-hash="${TELEGRAM_API_HASH}" \
    --dir=/var/lib/telegram-bot-api \
    --temp-dir=/tmp/telegram-bot-api \
    --http-port=8081 \
    --http-ip-address=127.0.0.1 \
    --local \
    --verbosity=1 &

  for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:8081/bot${BOT_TOKEN}/getMe" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

exec python run.py