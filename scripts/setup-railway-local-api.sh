#!/usr/bin/env bash
# Configure Railway services for Local Telegram Bot API (files > 50MB).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

API_ID="${TELEGRAM_API_ID:-}"
API_HASH="${TELEGRAM_API_HASH:-}"

if [[ -z "$API_ID" || -z "$API_HASH" ]]; then
  echo "Set TELEGRAM_API_ID and TELEGRAM_API_HASH before running this script."
  exit 1
fi

BOT_API_SERVICE="${BOT_API_SERVICE:-telegram-bot-api}"
BOT_SERVICE="${BOT_SERVICE:-bot}"

echo "==> Ensuring ${BOT_API_SERVICE} service exists"
if ! railway service status --service "$BOT_API_SERVICE" --json >/dev/null 2>&1; then
  railway add --service "$BOT_API_SERVICE" --repo carloostoek2/multibot2
fi

echo "==> Configuring ${BOT_API_SERVICE} build from docker/telegram-bot-api/Dockerfile"
railway environment edit \
  --service-config "$BOT_API_SERVICE" \
  build.builder DOCKERFILE
railway environment edit \
  --service-config "$BOT_API_SERVICE" \
  build.dockerfilePath "docker/telegram-bot-api/Dockerfile"

echo "==> Setting ${BOT_API_SERVICE} variables"
railway variable set \
  TELEGRAM_API_ID="$API_ID" \
  TELEGRAM_API_HASH="$API_HASH" \
  TELEGRAM_LOCAL=1 \
  TELEGRAM_HTTP_IP_ADDRESS=0.0.0.0 \
  --service "$BOT_API_SERVICE"

echo "==> Attaching persistent volume to ${BOT_API_SERVICE} (if missing)"
if ! railway volume list --service "$BOT_API_SERVICE" --json 2>/dev/null | grep -q '"name"'; then
  railway volume add --service "$BOT_API_SERVICE" --mount-path /var/lib/telegram-bot-api
fi

echo "==> Setting ${BOT_SERVICE} local API variables"
railway variable set \
  TELEGRAM_LOCAL_MODE=true \
  TELEGRAM_API_BASE_URL='http://${{telegram-bot-api.RAILWAY_PRIVATE_DOMAIN}}:${{telegram-bot-api.PORT}}/bot' \
  TELEGRAM_MAX_UPLOAD_SIZE_MB=2000 \
  DOWNLOAD_MAX_SIZE_MB=2000 \
  DOWNLOAD_MAX_SIZE_GENERIC_MB=2000 \
  TELEGRAM_API_TIMEOUT=120 \
  --service "$BOT_SERVICE"

echo "==> Deploying ${BOT_API_SERVICE}"
railway up --service "$BOT_API_SERVICE" --detach -m "Deploy local Telegram Bot API server"

echo "==> Deploying ${BOT_SERVICE}"
railway up --service "$BOT_SERVICE" --detach -m "Enable local Bot API for files > 50MB"

echo "Done. Check logs with:"
echo "  railway logs --service ${BOT_API_SERVICE} --lines 100"
echo "  railway logs --service ${BOT_SERVICE} --lines 100"