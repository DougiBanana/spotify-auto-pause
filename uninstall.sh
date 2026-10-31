#!/usr/bin/env bash
# spotify-auto-pause uninstaller
set -euo pipefail

APP="spotify-auto-pause"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$APP"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$APP"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
LINK="$HOME/.local/bin/$APP"
PURGE=0

for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=1 ;;
    -h|--help)
      echo "Usage: ./uninstall.sh [--purge]"
      echo "  --purge   also delete your config ($CONF_DIR)"
      exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 1 ;;
  esac
done

systemctl --user disable --now "$APP.service" >/dev/null 2>&1 || true
rm -f "$UNIT_DIR/$APP.service" "$LINK"
rm -rf "$DATA_DIR"
systemctl --user daemon-reload >/dev/null 2>&1 || true
systemctl --user reset-failed "$APP.service" >/dev/null 2>&1 || true

if [ "$PURGE" -eq 1 ]; then
  rm -rf "$CONF_DIR"
  echo "Removed $APP, including its config."
else
  echo "Removed $APP. Your config was kept at $CONF_DIR (use --purge to delete it)."
fi
