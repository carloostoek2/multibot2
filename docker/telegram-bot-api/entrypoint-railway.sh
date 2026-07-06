#!/bin/sh
set -e

# Railway injects PORT dynamically; aiogram image reads TELEGRAM_HTTP_PORT.
if [ -n "$PORT" ] && [ -z "$TELEGRAM_HTTP_PORT" ]; then
  export TELEGRAM_HTTP_PORT="$PORT"
fi

# Required for uploads/downloads beyond the 50MB cloud limit.
export TELEGRAM_LOCAL="${TELEGRAM_LOCAL:-1}"

# Listen on all interfaces inside Docker/Railway private networks.
export TELEGRAM_HTTP_IP_ADDRESS="${TELEGRAM_HTTP_IP_ADDRESS:-0.0.0.0}"

exec /docker-entrypoint.sh