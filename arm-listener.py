#!/usr/bin/env python3
"""Armed-mode key listener for browser-hotkey window switching.

Launched by window-switch.sh "arm" after the prefix hotkey. Grabs digit keys
(1..9) and Escape on the root window for N seconds; activates the matching
browser window (via wmctrl) or exits.
"""
import os
import subprocess
import sys
import time

from Xlib import X, XK, display

LOG = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "browser-hotkey.log")
CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "browser-hotkey/config.toml")
HERE = os.path.dirname(os.path.realpath(__file__))
LISTER = os.path.join(HERE, "list-windows.sh")


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%F %T')} arm: {msg}\n")


def cfg_value(key, default):
    try:
        with open(CONFIG) as f:
            for line in f:
                if line.strip().startswith(key):
                    return line.split("=", 1)[1].strip().strip('"').strip() or default
    except OSError:
        pass
    return default


def list_windows(scope):
    out = subprocess.run([LISTER, scope], capture_output=True, text=True).stdout.strip()
    rows = []
    for line in out.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3:
            rows.append((int(parts[0]), parts[1], parts[2]))
    return rows


def notify(title, body="", ms=2500):
    subprocess.run(["notify-send", "-t", str(ms), title, body], capture_output=True)


def activate(win_id):
    r = subprocess.run(["wmctrl", "-ia", win_id], capture_output=True)
    log(f"activated {win_id}" if r.returncode == 0 else f"activate {win_id} failed")
    return r.returncode == 0


def toggle_window(win_id):
    """Focus if not active; minimize if already the active window."""
    try:
        active = int(subprocess.run(
            ["xdotool", "getactivewindow"], capture_output=True, text=True
        ).stdout.strip())
    except ValueError:
        active = None
    hidden = "_NET_WM_STATE" in subprocess.run(
        ["xprop", "-id", win_id, "_NET_WM_STATE"], capture_output=True, text=True
    ).stdout and "HIDDEN" in subprocess.run(
        ["xprop", "-id", win_id, "_NET_WM_STATE"], capture_output=True, text=True
    ).stdout
    if active == int(win_id) and not hidden:
        subprocess.run(["xdotool", "windowminimize", win_id], capture_output=True)
        log(f"toggled -> minimize {win_id}")
        return True
    return activate(win_id)


def main():
    timeout = int("".join(c for c in cfg_value("timeout", "3") if c.isdigit()) or 3)
    scope = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else cfg_value("scope", "all")

    rows = list_windows(scope)
    if not rows:
        notify("Browser switch", "no browser windows")
        log("no windows")
        return 1

    listing = "\n".join(f"{i}: {t}" for i, _, t in rows)
    notify(f"Switch window — press 1-{len(rows)}", listing, ms=timeout * 1000)

    d = display.Display()
    root = d.screen().root

    keysyms = {}
    for k in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "Escape"):
        ks = XK.string_to_keysym(k)
        if ks != X.NoSymbol:
            keysyms[ks] = k

    # Grab digits with any modifier combo (bare, Alt, Shift, Ctrl, Super,
    # numlock/scrolllock variants) so holding Alt+Q and pressing 1/2 works,
    # and GNOME's leftover modifier state doesn't break the grab.
    mods = [0]
    for m in (X.Mod1Mask, X.ShiftMask, X.ControlMask, X.Mod4Mask, X.Mod5Mask):
        mods += [m, m | X.Mod2Mask]
    base = [0, X.Mod2Mask]
    combos = set(base)
    for m in mods:
        if m not in combos:
            combos.add(m)
    # also common pairs (Alt+Shift etc.)
    pairs = [X.Mod1Mask | X.ShiftMask, X.ControlMask | X.ShiftMask,
             X.Mod1Mask | X.ControlMask, X.Mod4Mask | X.ShiftMask]
    for pm in pairs:
        combos.add(pm)
        combos.add(pm | X.Mod2Mask)

    grabbed = []
    for ks in keysyms:
        codes = list(d.keysym_to_keycodes(ks))
        if not codes:
            continue
        code = codes[0][0]
        for mod in combos:
            try:
                root.grab_key(code, mod, True, X.GrabModeAsync, X.GrabModeAsync)
                grabbed.append((code, mod))
            except Exception:
                pass
    d.sync()

    deadline = time.time() + timeout
    result = None
    while result is None and time.time() < deadline:
        if d.pending_events() == 0:
            time.sleep(0.05)
            continue
        ev = d.next_event()
        if ev.type != X.KeyPress:
            continue
        ks = d.keycode_to_keysym(ev.detail, 0)
        key = keysyms.get(ks)
        if key == "Escape":
            log("cancelled (Esc)")
            result = 0
        elif key:
            win = next((w for i, w, _ in rows if i == int(key)), None)
            if win and toggle_window(win):
                result = 0
            elif win:
                result = 1
            else:
                notify("Browser switch", f"no window #{key}", ms=1200)
                log(f"no window #{key}")
                result = 1
        # any other key: keep waiting
    if result is None:
        notify("Browser switch", "timeout", ms=800)
        log("timeout")

    for code, mod in set(grabbed):
        try:
            root.ungrab_key(code, mod, root)
        except Exception:
            pass
    d.sync()
    d.close()
    return 0 if result == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
