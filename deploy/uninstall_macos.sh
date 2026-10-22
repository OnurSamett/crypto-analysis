#!/bin/bash
# launchd görevlerini kaldırır (veri ve durum dosyalarına dokunmaz).
set -euo pipefail
for name in notify collect; do
  label="com.onursamett.crypto-analysis.$name"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/$label.plist"
  echo "kaldırıldı: $label"
done
