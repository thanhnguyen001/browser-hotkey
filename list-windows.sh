#!/usr/bin/env bash
# List a browser's windows in stable order (oldest window = 1).
# Usage: list-windows.sh <firefox|google-chrome|microsoft-edge|all>
# Output: "<index> <window_id_decimal> <title>" per line.
set -u

case "${1:-}" in
  firefox)        classes="Navigator|firefox" ;;
  google-chrome)  classes="Google-chrome|google-chrome" ;;
  microsoft-edge) classes="Microsoft-edge|microsoft-edge" ;;
  all)            classes="Navigator|firefox|Google-chrome|google-chrome|Microsoft-edge|microsoft-edge" ;;
  *) echo "usage: $0 <firefox|google-chrome|microsoft-edge|all>" >&2; exit 1 ;;
esac

# Only windows wmctrl lists are real toplevels (skip Chromium internal slots).
# wmctrl -l: 0xID  workspace  host  title...
declare -A TITLES
while read -r wid _ws _host rest; do
  TITLES[$((wid))]="$(echo "$rest" | sed 's/^ *//')"
done < <(wmctrl -l)

i=0
while read -r h; do
  dec=$((h))
  [[ -n "${TITLES[$dec]:-}" ]] || continue   # not a managed toplevel
  i=$((i+1))
  echo "$i $dec ${TITLES[$dec]}"
done < <(xdotool search --class "$classes" 2>/dev/null | sort -n)
