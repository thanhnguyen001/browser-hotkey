#!/usr/bin/env bash
# Close or minimize all windows of a browser (X11).
# Usage: browser-action.sh <firefox|google-chrome|microsoft-edge> <close|minimize>
set -u

LOG="${XDG_DATA_HOME:-$HOME/.local/share}/browser-hotkey.log"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/browser-hotkey/config.toml"

browser="$1"
action="$2"

log() { echo "$(date '+%F %T') action $browser $action: $*" >> "$LOG"; }

# Resolve window class from browser name
case "$browser" in
  firefox)        class="firefox|Firefox" ;;
  google-chrome)  class="google-chrome|Google-chrome" ;;
  microsoft-edge) class="microsoft-edge|Microsoft-edge" ;;
  *) log "unknown browser '$browser'"; exit 1 ;;
esac

# Read per-browser override from config (action only)
if [[ -f "$CONFIG" ]]; then
  cfg=$(awk -v b="$browser" '
    $0 == "["b"]" {in_b=1; next}
    /^\[/ {in_b=0}
    in_b && $1 == "action" {gsub(/[" ]/,"",$3); print $3}
  ' "$CONFIG")
  [[ "$cfg" == "close" || "$cfg" == "minimize" ]] && action="$cfg"
fi

# Only managed toplevel windows (wmctrl-listed); skip Chromium hidden slots
declare -A TOPS
while read -r wid _ws _host _rest; do TOPS[$((wid))]=1; done < <(wmctrl -l)
ids=""
for h in $(xdotool search --class "$class" 2>/dev/null); do
  [[ -n "${TOPS[$((h))]:-}" ]] && ids="$ids $h"
done
ids=${ids# }
[[ -z "$ids" ]] && { log "no window found"; exit 1; }

# toggle: if any window is visible -> minimize all; else activate all
is_visible() { # 1 if window not hidden
  xprop -id "$1" _NET_WM_STATE 2>/dev/null | grep -q HIDDEN && return 1 || return 0
}

case "$action" in
  close|minimize)
    fail=0
    for id in $ids; do
      case "$action" in
        close)    wmctrl -ic "$id" || fail=1 ;;
        minimize) xdotool windowminimize "$id" || fail=1 ;;
      esac
    done
    log "$action ok ($(echo "$ids" | wc -l) window(s))"
    exit $fail
    ;;
  activate)
    ok=0
    for id in $ids; do is_visible "$id" || { wmctrl -ia "$id"; ok=1; } ; done
    log "activate ok ($ok restored)"
    exit 0
    ;;
  toggle)
    any_visible=0
    for id in $ids; do is_visible "$id" && any_visible=1; done
    if [[ $any_visible -eq 1 ]]; then
      for id in $ids; do xdotool windowminimize "$id"; done
      log "toggle -> minimize ($(echo "$ids" | wc -l) window(s))"
    else
      for id in $ids; do wmctrl -ia "$id"; done
      log "toggle -> activate ($(echo "$ids" | wc -l) window(s))"
    fi
    exit 0
    ;;
  *) log "unknown action '$action'"; exit 1 ;;
esac
