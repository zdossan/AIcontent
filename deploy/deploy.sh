#!/usr/bin/env bash
# Кодты серверге жіберіп, ботты қайта қосу. Mac-тан орындалады:
#   ./deploy/deploy.sh ubuntu@SERVER_IP
set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
    echo "Қолданылуы: $0 ubuntu@SERVER_IP" >&2
    exit 1
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR=/opt/aicontent-bot
APP_USER=aicontent
RSYNC_ROOT=(--rsync-path="sudo rsync")

if [[ ! -f "$HERE/.env" ]]; then
    echo "$HERE/.env жоқ. .env.example үлгісімен жасаңыз." >&2
    exit 1
fi

echo "==> Кодты жіберу: $TARGET:$APP_DIR"
# --delete тек bot/ ішіне қатысты. Дерекқор APP_DIR түбірінде жатыр,
# сондықтан оған тиіспейді.
rsync -az --delete "${RSYNC_ROOT[@]}" \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '*.db' \
    "$HERE/bot" "$HERE/requirements.txt" \
    "$TARGET:$APP_DIR/"

echo "==> .env жіберу"
rsync -az "${RSYNC_ROOT[@]}" "$HERE/.env" "$TARGET:$APP_DIR/.env"

if [[ -f "$HERE/google-credentials.json" ]]; then
    echo "==> Google service account кілтін жіберу"
    rsync -az "${RSYNC_ROOT[@]}" "$HERE/google-credentials.json" \
        "$TARGET:$APP_DIR/google-credentials.json"
fi

echo "==> systemd сервисін жіберу"
rsync -az "${RSYNC_ROOT[@]}" "$HERE/deploy/aicontent-bot.service" \
    "$TARGET:/etc/systemd/system/aicontent-bot.service"

echo "==> Тәуелділіктерді орнату + сервисті қосу"
ssh "$TARGET" sudo bash -euo pipefail <<REMOTE
    cd $APP_DIR
    if [[ ! -x .venv/bin/python ]]; then
        python3 -m venv .venv
    fi
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
    chown -R $APP_USER:$APP_USER $APP_DIR
    chmod 600 $APP_DIR/.env
    [[ -f $APP_DIR/google-credentials.json ]] && chmod 600 $APP_DIR/google-credentials.json

    systemctl daemon-reload
    systemctl enable --now aicontent-bot
    systemctl restart aicontent-bot
    sleep 3
    systemctl --no-pager --lines=0 status aicontent-bot | head -5
REMOTE

echo
echo "==> Дайын. Логтар: ssh $TARGET 'journalctl -u aicontent-bot -f'"
