#!/usr/bin/env bash
# Серверді бір рет дайындау. Серверде root атынан орындалады:
#   bash setup.sh
set -euo pipefail

APP_DIR=/opt/aicontent-bot
APP_USER=aicontent

echo "==> python3-venv тексеру"
if ! dpkg -s python3-venv >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq python3-venv
fi

echo "==> $APP_USER қолданушысын жасау"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"

echo "==> $APP_DIR дайындау"
mkdir -p "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> Дайын. Енді Mac-тан ./deploy/deploy.sh ubuntu@SERVER_IP орындаңыз."
