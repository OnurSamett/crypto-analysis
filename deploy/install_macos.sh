#!/bin/bash
# Mac mini'de bildirim ve veri toplayıcıyı launchd'ye kurar. Önce deploy/README.md adımlarını izleyin.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "Önce sanal ortamı kurun: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }
[ -f "$REPO/.env" ] || { echo ".env yok. .env.example dosyasını kopyalayıp TELEGRAM_* değerlerini doldurun."; exit 1; }
LOGS="$HOME/Library/Logs/crypto-analysis"; mkdir -p "$LOGS"
AGENTS="$HOME/Library/LaunchAgents"; mkdir -p "$AGENTS"
for name in notify collect; do
  label="com.onursamett.crypto-analysis.$name"
  dst="$AGENTS/$label.plist"
  sed -e "s|__REPO__|$REPO|g" -e "s|__PY__|$PY|g" -e "s|__LOGS__|$LOGS|g" "$REPO/deploy/macos/$label.plist" > "$dst"
  plutil -lint "$dst" >/dev/null
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$dst"
  launchctl enable "gui/$(id -u)/$label"
  echo "kuruldu: $label"
done
echo "Günlükler: $LOGS"
