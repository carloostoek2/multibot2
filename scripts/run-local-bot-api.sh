#!/usr/bin/env bash
# Launch Local Telegram Bot API for Multibot2 (loopback only).
set -euo pipefail
ENV_FILE="${HOME}/repos/multibot2/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
if [[ -z "${TELEGRAM_API_ID:-}" || -z "${TELEGRAM_API_HASH:-}" ]]; then
  echo "TELEGRAM_API_ID and TELEGRAM_API_HASH required in .env" >&2
  exit 1
fi
mkdir -p "${HOME}/data/multibot2/telegram-bot-api" "${HOME}/data/multibot2/telegram-bot-api-tmp"
exec "${HOME}/bin/telegram-bot-api" \
  --api-id="${TELEGRAM_API_ID}" \
  --api-hash="${TELEGRAM_API_HASH}" \
  --local \
  --dir="${HOME}/data/multibot2/telegram-bot-api" \
  --temp-dir="${HOME}/data/multibot2/telegram-bot-api-tmp" \
  --http-port=8081 \
  --http-ip-address=127.0.0.1 \
  --verbosity=1
