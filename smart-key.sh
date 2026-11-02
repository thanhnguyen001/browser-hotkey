#!/usr/bin/env bash
# Smart per-browser key:
#   - 0 windows  -> nothing
#   - 1 window   -> toggle it (minimize/restore)
#   - >=2 windows -> numbered picker, press 1..9 to open exactly that window
# Usage: smart-key.sh <firefox|google-chrome|microsoft-edge>
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG="${XDG_DATA_HOME:-$HOME/.local/share}/browser-hotkey.log"
log() { echo "$(date '+%F %T') smart[$1]: $*" >> "$LOG"; }

browser="${1:-}"
n=$("$HERE/list-windows.sh" "$browser" 2>/dev/null | wc -l)
case "$n" in
  0) log "no windows"; exit 0 ;;
  1) exec "$HERE/browser-action.sh" "$browser" toggle ;;
  *) exec "$HERE/window-switch.sh" arm "$browser" ;;
esac
