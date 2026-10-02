#!/usr/bin/env bash
set -euo pipefail
systemctl --user stop multibot2-bot.service || true
systemctl --user stop multibot2-local-api.service || true
systemctl --user disable multibot2-bot.service multibot2-local-api.service || true
echo "EC2 Multibot2 stopped. Redeploy/start Railway bot service to resume."
