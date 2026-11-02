#!/usr/bin/env bash
# Install browser-hotkey: copy scripts, sync config, register GNOME keybindings
# from keys.toml (single source of truth for all shortcuts).
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
BIN="$HOME/.local/bin"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/browser-hotkey"
VENV="$HOME/.local/share/browser-hotkey-venv"
KEYS="$HERE/keys.toml"

mkdir -p "$BIN" "$CONF_DIR"
install -m 755 "$HERE/browser-action.sh" "$HERE/list-windows.sh" "$HERE/window-switch.sh" "$HERE/smart-key.sh" "$HERE/arm-listener.py" "$BIN/"
[[ -f "$KEYS" ]] || { echo "missing $KEYS" >&2; exit 1; }
cp "$KEYS" "$CONF_DIR/keys.toml"
[[ -f "$CONF_DIR/config.toml" ]] || install -m 644 "$HERE/config.toml" "$CONF_DIR/config.toml"

if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q python-xlib
fi
echo "Installed scripts to $BIN and venv to $VENV"

# --- parse keys.toml: get(section, field) → value without quotes ---
tget() { # tget <section> <field>
  awk -v s="[$1]" -v f="$2" '
    $0 == s {in_s=1; next}
    /^\[/ {in_s=0}
    in_s && $1 == f {sub(/#.*/,""); gsub(/[" ]/,""); n=split($0,a,"="); print a[2]; exit}
  ' "$KEYS"
}

# --- GNOME keybindings ---
GSD=org.gnome.settings-daemon.plugins.media-keys
remove_from_list() { # remove_from_list <name> — drop a stale custom-keybindings entry
  local name="$1"
  local existing
  existing=$(gsettings get "$GSD" custom-keybindings)
  case "$existing" in
    *"$name"*) ;;
    *) return 0 ;;
  esac
  local keep
  keep=$(echo "$existing" | tr -d "'" | tr -d '[]' | tr ',' '\n' | sed "s| ||g" | grep -v "$name" | sed "s|\(.*\)|'\1'|" | paste -sd, -)
  if [[ -z "$keep" ]]; then
    gsettings set "$GSD" custom-keybindings "@as []"
  else
    gsettings set "$GSD" custom-keybindings "[$keep]"
  fi
}

register() { # register <name> <command> <accel>
  local path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/$1/"
  local existing
  existing=$(gsettings get "$GSD" custom-keybindings)
  case "$existing" in
    *"$1"*) : ;;
    ""|"@as []"|"[]") gsettings set "$GSD" custom-keybindings "['$path']" ;;
    *) gsettings set "$GSD" custom-keybindings "${existing%\]},'$path']" ;;
  esac
  local schema_path="$GSD.custom-keybinding:$path"
  gsettings set "$schema_path" name "$1"
  gsettings set "$schema_path" command "$2"
  gsettings set "$schema_path" binding "$3"
}

# Resident daemon mode: daemon grabs prefix keys itself (zero-latency),
# so GNOME must NOT bind the same keys.
DAEMON=1
AUTOSTART="$HOME/.config/autostart/browser-hotkey-daemon.desktop"

if [[ "$DAEMON" -eq 1 ]]; then
  install -m 755 "$HERE/hotkey-daemon.py" "$BIN/hotkey-daemon.py"
  mkdir -p "$(dirname "$AUTOSTART")"
  cat > "$AUTOSTART" <<DESK
[Desktop Entry]
Type=Application
Name=browser-hotkey-daemon
Exec=$VENV/bin/python $BIN/hotkey-daemon.py
X-GNOME-Autostart-enabled=true
DESK
  # stop stale instance, start fresh
  pkill -f hotkey-daemon.py 2>/dev/null; sleep 0.5
  nohup "$VENV/bin/python" "$BIN/hotkey-daemon.py" >/dev/null 2>&1 &
  echo "Daemon mode: hotkey-daemon started (autostart at login)."
  echo "GNOME keybindings for prefix keys are intentionally NOT registered"
  echo "(daemon owns them). Action keys (close/minimize etc.) still below."
fi

echo "Registered keybindings (from $KEYS):"
for b in firefox google-chrome microsoft-edge; do
  key=$(tget "$b" key)
  act=$(tget "$b" action)
  if [[ -n "$key" && "$DAEMON" -eq 1 && "$act" == "smart" ]]; then
    # daemon handles prefix+digit; but single-window toggle also needs a key:
    # smart-key.sh fallback only when window count is 1 -> register via daemon?
    # Daemon handles toggle itself on digit press (digit with 1 window toggles it).
    remove_from_list "bh-$b"
    echo "  $key  -> $b: DAEMON (hold key + 1-9 to switch; key alone + digit toggles)"
  elif [[ -n "$key" ]]; then
    if [[ "$act" == "smart" ]]; then
      register "bh-$b" "$BIN/smart-key.sh $b" "$key"
      echo "  $key  -> $b: smart (1 window: toggle; 2+: picker 1-9)"
    else
      register "bh-$b" "$BIN/browser-action.sh $b $act" "$key"
      echo "  $key  -> $b: $act (all windows)"
    fi
  fi

  kw=$(tget "$b" key_window)
  if [[ "$DAEMON" -eq 1 && ( "$act" == "smart" || "$kw" == "none" ) ]]; then
    remove_from_list "bh-$b-win"
  elif [[ -n "$kw" && "$kw" != "none" ]]; then
    register "bh-$b-win" "$BIN/window-switch.sh arm $b" "$kw"
    echo "  $kw  -> $b: pick window (then 1-9)"
  else
    # key disabled -> remove stale binding from GNOME list if present
    remove_from_list "bh-$b-win"
  fi
done

gkey=$(tget switch key)
if [[ "$DAEMON" -eq 1 ]]; then
  # daemon grabs the switch prefix itself
  remove_from_list "bh-switch"
  echo "  $gkey  -> ALL browsers: DAEMON picker (hold + 1-9)"
else
  [[ -n "$gkey" && "$gkey" != "none" ]] && { register "bh-switch" "$BIN/window-switch.sh arm all" "$gkey"
    echo "  $gkey  -> switch across ALL browsers (then 1-9)"; }
fi
