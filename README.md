# browser-hotkey

Global hotkeys for Ubuntu (GNOME, X11) to close/minimize browsers and switch
between numbered browser windows.

## Features

- **Per-browser action key**: one shortcut closes, minimizes, restores, or
  toggles that browser (`toggle` = minimize when visible, restore when
  minimized — press the same key again to bring it back)
- **Per-browser window picker**: when a browser has ≥ 2 windows, press its
  picker key, an on-screen list shows `1: <title>`, `2: <title>` …, press the
  number to open exactly that window. `Esc` / 3 s timeout cancels.
- **Global picker** across all browsers
- All shortcuts defined in **one file**: `keys.toml`
- Logs to `~/.local/share/browser-hotkey.log`

## Requirements

- Ubuntu with X11 session (check: `echo $XDG_SESSION_TYPE` — must be `x11`)
- `xdotool`, `wmctrl`, `notify-send`, `python3` (+`venv`), `flock`, GNOME
  (`gsettings`). Installer creates a private venv with `python-xlib` — system
  Python untouched.

## Install

```bash
cd browser-hotkey
./install.sh
```

## Shortcut settings — `keys.toml`

**Single source of truth** for keys, actions, and pickers. Located at
`~/workspace/study/tools/browser-hotkey/keys.toml` (copied to
`~/.config/browser-hotkey/keys.toml` on install).

```toml
[firefox]
key        = "<Ctrl><Shift>b"    # action key
action     = "toggle"            # close | minimize | activate | toggle
key_window = "<Ctrl><Alt>b"      # window picker for Firefox only

[google-chrome]
key        = "<Ctrl><Shift>c"
action     = "toggle"
key_window = "<Ctrl><Alt>c"

[microsoft-edge]
key        = "<Ctrl><Shift>e"
action     = "toggle"
key_window = "<Ctrl><Alt>e"

[switch]
key     = "<Ctrl><Shift>q"       # global picker, all browsers
timeout = 3                      # seconds to wait for the number key
```

After editing: rerun `./install.sh` — it re-reads keys.toml and updates the
GNOME keybindings. Set a key to `none` (or delete the line) to skip it.

Key syntax: `<Ctrl>`, `<Shift>`, `<Alt>`, `<Super>` + letter/number/F-key.

## Default bindings

| Keys | Action |
|---|---|
| `Ctrl+Shift+B` | toggle Firefox (minimize ↔ restore) |
| `Ctrl+Alt+B` | Firefox window picker → `1`–`9` |
| `Ctrl+Shift+C` | toggle Chrome (minimize ↔ restore) |
| `Ctrl+Alt+C` | Chrome window picker → `1`–`9` |
| `Ctrl+Shift+E` | toggle Edge (minimize ↔ restore) |
| `Ctrl+Alt+E` | Edge window picker → `1`–`9` |
| `Ctrl+Shift+Q` | global picker (all browsers) → `1`–`9` |

Window numbering is stable: oldest window = 1.

## Behavior config — `config.toml`

`~/.config/browser-hotkey/config.toml` (rarely needed — keys.toml covers most
settings): default `scope`/`timeout` fallbacks for direct CLI use.

## CLI usage without keybindings

```bash
browser-action.sh firefox close           # close all Firefox windows
browser-action.sh firefox toggle         # minimize if visible, restore if not
browser-action.sh google-chrome minimize # minimize all Chrome windows
window-switch.sh firefox 2               # open Firefox window #2
window-switch.sh arm firefox             # picker mode for Firefox
window-switch.sh arm all                 # global picker
list-windows.sh all                      # list windows with indices
```

## How it works

- Action key → `browser-action.sh` (`wmctrl -ic` graceful close,
  `xdotool windowminimize`).
- Picker key → `arm-listener.py` (Xlib `XGrabKey` on root): grabs `1`–`9` +
  `Esc` only for the timeout duration, then releases — normal typing is never
  affected. Single instance guarded by `flock`.
- Windows matched by WM_CLASS (`Navigator`/`firefox`, `Google-chrome`,
  `Microsoft-edge`); hidden Chromium slot windows filtered out.

## Limitations

- X11 only (no Wayland support).
- "Close multiple tabs?" browser dialogs are respected — disable the prompt in
  browser settings for instant close.
- Private/incognito windows share WM_CLASS and are included.
