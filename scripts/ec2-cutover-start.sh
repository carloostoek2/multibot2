#!/usr/bin/env bash
# ONLY run AFTER Railway Multibot2 bot service is stopped.
set -euo pipefail
ENV_FILE="${HOME}/repos/multibot2/.env"
set -a; source "$ENV_FILE"; set +a
if [[ -z "${BOT_TOKEN:-}" ]]; then echo "BOT_TOKEN empty — abort"; exit 1; fi
if [[ "${TELEGRAM_LOCAL_MODE:-}" == "true" ]]; then
  if [[ -z "${TELEGRAM_API_ID:-}" || -z "${TELEGRAM_API_HASH:-}" ]]; then
    echo "Local mode requires API_ID/HASH — abort"; exit 1
  fi
fi
systemctl --user daemon-reload
systemctl --user enable multibot2-local-api.service multibot2-bot.service
systemctl --user start multibot2-local-api.service
# wait for local API port
for i in $(seq 1 30); do
  if ss -tln | grep -q "127.0.0.1:8081"; then break; fi
  sleep 1
done
systemctl --user start multibot2-bot.service
systemctl --user --no-pager status multibot2-local-api.service multibot2-bot.service | cat
journalctl --user -u multibot2-bot -u multibot2-local-api -n 40 --no-pager | cat
