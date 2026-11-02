#!/usr/bin/env bash
# Window switcher entry point.
#   window-switch.sh arm            -> prefix mode: show numbers, wait for digit
#   window-switch.sh <scope> <n>    -> direct: activate window n (for static bindings)
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$HOME/.local/share/browser-hotkey-venv/bin/python"
FALLBACK_PY="$(command -v python3)"
PY="$VENV_PY"; [[ -x "$PY" ]] || PY="$FALLBACK_PY"

LOG="${XDG_DATA_HOME:-$HOME/.local/share}/browser-hotkey.log"
log() { echo "$(date '+%F %T') switch: $*" >> "$LOG"; }

if [[ "${1:-}" == "arm" ]]; then
  exec 9>/tmp/browser-hotkey.lock
  flock -n 9 || { log "already armed"; exit 0; }
  exec "$PY" "$HERE/arm-listener.py" "${2:-}"
fi

# Direct mode
if [[ $# -eq 2 && "$2" =~ ^[0-9]+$ ]]; then
  id=$("$HERE/list-windows.sh" "$1" | awk -v n="$2" '$1==n {print $2}')
  if [[ -z "$id" ]]; then
    log "no window #$2 for $1"; notify-send -t 1500 "Browser switch" "No window #$2" 2>/dev/null
    exit 1
  fi
  wmctrl -ia "$id" && log "activated $id ($1 #$2)"
  exit $?
fi

echo "usage: $0 arm | <firefox|google-chrome|microsoft-edge|all> <index>" >&2
exit 1
