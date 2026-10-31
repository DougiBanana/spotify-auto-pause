#!/usr/bin/env bash
# spotify-auto-pause installer (per-user, no root needed except to install missing packages)
set -euo pipefail

APP="spotify-auto-pause"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$APP"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$APP"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
LINK="$HOME/.local/bin/$APP"
ASSUME_YES=0

info() { printf '\033[1;34m::\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m  %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m  %s\n' "$*" >&2; }
die()  { printf '\033[1;31mx\033[0m  %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Usage: ./install.sh [-y|--yes]

Installs $APP for the current user:
  script   -> $DATA_DIR
  config   -> $CONF_DIR/config.json (kept if it already exists)
  service  -> $UNIT_DIR/$APP.service (enabled and started)

  -y, --yes   install missing packages without asking
EOF
}

for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $arg (try --help)" ;;
  esac
done

[ "$(id -u)" -ne 0 ] || die "Do not run this as root: it installs a per-user service. Run it as your normal user."
command -v systemctl >/dev/null 2>&1 || die "systemd is required (systemctl not found)."
systemctl --user show-environment >/dev/null 2>&1 \
  || die "No systemd user session found. Run this from a normal desktop login session."
[ -f "$SRC_DIR/$APP.py" ] || die "$APP.py not found next to install.sh."
[ -f "$SRC_DIR/config.example.json" ] || die "config.example.json not found next to install.sh."

# ---------------------------------------------------------------- dependencies
detect_pm() {
  local pm
  for pm in pacman apt-get dnf zypper; do
    if command -v "$pm" >/dev/null 2>&1; then echo "$pm"; return 0; fi
  done
  return 1
}

pkg_for() { # $1 = command, $2 = package manager
  case "$1:$2" in
    python3:pacman) echo python ;;
    python3:*)      echo python3 ;;
    playerctl:*)    echo playerctl ;;
    pactl:pacman)   echo libpulse ;;
    pactl:*)        echo pulseaudio-utils ;;
  esac
}

set_install_cmd() { # sets the INSTALL array for package manager $1
  case "$1" in
    pacman)  INSTALL=(sudo pacman -S --needed) ;;
    apt-get) INSTALL=(sudo apt-get install -y) ;;
    dnf)     INSTALL=(sudo dnf install -y) ;;
    zypper)  INSTALL=(sudo zypper install -y) ;;
  esac
}

missing=()
for c in python3 playerctl pactl; do
  command -v "$c" >/dev/null 2>&1 || missing+=("$c")
done

if [ "${#missing[@]}" -gt 0 ]; then
  warn "Missing dependencies: ${missing[*]}"
  pm="$(detect_pm || true)"
  [ -n "$pm" ] || die "Install them with your package manager (pactl comes from the PulseAudio utils) and run this again."

  pkgs=()
  for c in "${missing[@]}"; do pkgs+=("$(pkg_for "$c" "$pm")"); done
  INSTALL=()
  set_install_cmd "$pm"
  echo "   ${INSTALL[*]} ${pkgs[*]}"

  answer="n"
  if [ "$ASSUME_YES" -eq 1 ]; then
    answer="y"
  elif [ -t 0 ]; then
    read -r -p "Run this command now? [y/N] " answer || answer="n"
  fi
  case "$answer" in
    y|Y|yes|YES) "${INSTALL[@]}" "${pkgs[@]}" ;;
    *) die "Install the dependencies above and run ./install.sh again." ;;
  esac

  for c in python3 playerctl pactl; do
    command -v "$c" >/dev/null 2>&1 || die "'$c' is still missing after the installation."
  done
fi
ok "Dependencies found (python3, playerctl, pactl)"

if pactl info >/dev/null 2>&1 && ! pactl -f json info >/dev/null 2>&1; then
  warn "Your pactl has no JSON output (needs PulseAudio 15+ or PipeWire with pipewire-pulse). The tool will not work."
fi

# --------------------------------------------------------------------- install
info "Installing files"
mkdir -p "$DATA_DIR" "$CONF_DIR" "$UNIT_DIR" "$(dirname "$LINK")"
install -m 0755 "$SRC_DIR/$APP.py" "$DATA_DIR/$APP.py"
ln -sf "$DATA_DIR/$APP.py" "$LINK"

if [ -f "$CONF_DIR/config.json" ]; then
  ok "Keeping your existing config: $CONF_DIR/config.json"
else
  install -m 0644 "$SRC_DIR/config.example.json" "$CONF_DIR/config.json"
  ok "Created config: $CONF_DIR/config.json"
fi

cat > "$UNIT_DIR/$APP.service" <<EOF
[Unit]
Description=Pause Spotify automatically when other apps play audio
After=pipewire.service pipewire-pulse.service pulseaudio.service

[Service]
ExecStart=/usr/bin/env python3 "$DATA_DIR/$APP.py"
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

info "Enabling the service"
systemctl --user daemon-reload
systemctl --user enable "$APP.service" >/dev/null 2>&1
systemctl --user restart "$APP.service"
sleep 1

if systemctl --user is-active --quiet "$APP.service"; then
  ok "Service is running and will start at every login"
else
  warn "The service did not start. Check the log with:  journalctl --user -u $APP -n 30"
fi

cat <<EOF

Done. Next steps:
  * See which apps are playing audio and how they are treated:
      $LINK --list
  * Edit the settings (then restart the service):
      $CONF_DIR/config.json
      systemctl --user restart $APP
  * Live log:
      journalctl --user -u $APP -f
EOF

case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) warn "$HOME/.local/bin is not in your PATH; use the full path shown above to run --list." ;;
esac
