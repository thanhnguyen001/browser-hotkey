#!/usr/bin/env python3
"""Resident hotkey daemon for browser-hotkey.

Permanently grabs the configured prefix keys (e.g. <Alt>q). On prefix press
it instantly grabs digit keys (all modifier combos) for `timeout` seconds,
so holding Alt+Q and pressing 1/2 NEVER leaks to the focused app (YouTube
seek etc.). Digit toggles the numbered window (focus if idle, minimize if
active). Esc cancels.

Because prefixes are owner_events=False grabs, GNOME bindings for the same
keys must NOT be registered (install.sh handles that when daemon=enabled).
"""
import os
import re
import subprocess
import sys
import time

from Xlib import X, XK, display

HERE = os.path.dirname(os.path.realpath(__file__))
LOG = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "browser-hotkey.log")
KEYS = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "browser-hotkey/keys.toml")
LISTER = os.path.join(HERE, "list-windows.sh")

MODS = {
    "ctrl": X.ControlMask, "shift": X.ShiftMask, "alt": X.Mod1Mask,
    "super": X.Mod4Mask, "meta": X.Mod4Mask,
}


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%F %T')} daemon: {msg}\n")


def parse_accel(accel):
    """'<Alt><Shift>q' -> (keysym, modmask)"""
    mods = 0
    for m in re.findall(r"<(.*?)>", accel):
        mods |= MODS[m.lower()]
    key = re.sub(r"<.*?>", "", accel).strip()
    ks = XK.string_to_keysym(key if len(key) == 1 else key.capitalize() if key.islower() else key)
    if ks == X.NoSymbol and len(key) == 1:
        ks = XK.string_to_keysym(key.lower())
    return ks, mods


def load_config():
    """-> (prefix_map, timeout)
    prefix_map: {keysym+mods: browser_scope} ; scope 'all' or browser name"""
    prefixes, timeout, section = {}, 3, None
    browsers = {"firefox", "google-chrome", "microsoft-edge"}
    with open(KEYS) as f:
        for line in f:
            t = line.strip()
            if t.startswith("["):
                section = t.strip("[]")
                continue
            if "=" not in t:
                continue
            k, v = t.split("=", 1)
            k, v = k.strip(), v.split("#")[0].strip().strip('"')
            if section == "switch":
                if k == "timeout":
                    timeout = int("".join(c for c in v if c.isdigit()) or 3)
                elif k == "key" and v and v != "none":
                    ks, m = parse_accel(v)
                    if ks != X.NoSymbol:
                        prefixes[(ks, m)] = "all"
            elif section in browsers:
                # smart mode or explicit key_window handled by daemon
                # (smart: the action key doubles as the picker prefix)
                if k == "key" and v and v != "none":
                    ks, m = parse_accel(v)
                    if ks != X.NoSymbol:
                        prefixes[(ks, m)] = section
    return prefixes, timeout


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
    try:
        active = int(subprocess.run(["xdotool", "getactivewindow"],
                                    capture_output=True, text=True).stdout.strip())
    except ValueError:
        active = None
    state = subprocess.run(["xprop", "-id", win_id, "_NET_WM_STATE"],
                           capture_output=True, text=True).stdout
    hidden = "HIDDEN" in state
    if active == int(win_id) and not hidden:
        subprocess.run(["xdotool", "windowminimize", win_id], capture_output=True)
        log(f"toggled -> minimize {win_id}")
        return True
    return activate(win_id)


def all_mod_combos():
    combos = {0, X.Mod2Mask, X.Mod5Mask, X.Mod2Mask | X.Mod5Mask}
    singles = [X.Mod1Mask, X.ShiftMask, X.ControlMask, X.Mod4Mask]
    pairs = [X.Mod1Mask | X.ShiftMask, X.ControlMask | X.ShiftMask,
             X.Mod1Mask | X.ControlMask, X.Mod4Mask | X.ShiftMask]
    for m in singles + pairs:
        combos.add(m)
        combos.add(m | X.Mod2Mask)
        combos.add(m | X.Mod5Mask)
    return combos


def main():
    prefixes, timeout = load_config()
    d = display.Display()
    root = d.screen().root
    root.change_attributes(event_mask=X.KeyPressMask)

    # permanent prefix grabs (all lock-mask variants)
    prefix_codes = {}  # (code, mod) -> scope
    for (ks, mods), scope in prefixes.items():
        codes = list(d.keysym_to_keycodes(ks))
        if not codes:
            log(f"no keycode for keysym {ks}")
            continue
        code = codes[0][0]
        for lock in (0, X.Mod2Mask, X.Mod5Mask, X.Mod2Mask | X.Mod5Mask):
            try:
                root.grab_key(code, mods | lock, False, X.GrabModeAsync, X.GrabModeAsync)
                prefix_codes[(code, mods | lock)] = scope
            except Exception as e:
                log(f"grab prefix failed: {e}")
    d.sync()
    log(f"resident: {len(prefix_codes)} prefix grabs, timeout={timeout}s")

    digit_ks = {}
    for n in [str(i) for i in range(1, 10)]:
        ks = XK.string_to_keysym(n)
        if ks != X.NoSymbol:
            digit_ks[ks] = n
    esc_ks = XK.string_to_keysym("Escape")
    digit_combos = all_mod_combos()

    def grab_digits():
        got = []
        for ks in list(digit_ks) + [esc_ks]:
            codes = list(d.keysym_to_keycodes(ks))
            if not codes:
                continue
            code = codes[0][0]
            for mod in digit_combos:
                try:
                    root.grab_key(code, mod, False, X.GrabModeAsync, X.GrabModeAsync)
                    got.append((code, mod))
                except Exception:
                    pass
        return got

    def ungrab(got):
        for code, mod in set(got):
            try:
                root.ungrab_key(code, mod, root)
            except Exception:
                pass
        d.sync()

    while True:
        ev = d.next_event()
        if ev.type != X.KeyPress:
            continue
        scope = prefix_codes.get((ev.detail, ev.state & ~ev.state))  # exact match may miss masks
        if scope is None:
            # tolerate extra lock bits in state
            for (code, mod), sc in prefix_codes.items():
                if code == ev.detail and (ev.state & mod) == mod:
                    scope = sc
                    break
        if scope is None:
            continue

        rows = list_windows(scope)
        if not rows:
            notify("Browser switch", "no windows")
            log(f"prefix {scope}: no windows")
            continue

        if len(rows) == 1:
            # single window: prefix alone toggles it (smart behavior)
            toggle_window(rows[0][1])
            continue

        listing = "\n".join(f"{i}: {t}" for i, _, t in rows)
        notify(f"Switch window — press 1-{len(rows)} (Esc cancels)", listing, ms=timeout * 1000)
        log(f"armed scope={scope} windows={len(rows)}")

        got = grab_digits()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if d.pending_events() == 0:
                time.sleep(0.03)
                continue
            e2 = d.next_event()
            if e2.type != X.KeyPress:
                continue
            ks = d.keycode_to_keysym(e2.detail, 0)
            if ks == esc_ks:
                log("cancelled (Esc)")
                break
            n = digit_ks.get(ks)
            if n:
                win = next((w for i, w, _ in rows if i == int(n)), None)
                if win:
                    toggle_window(win)
                else:
                    notify("Browser switch", f"no window #{n}", ms=1200)
                break
            # other keys keep waiting
        else:
            log("timeout")
        ungrab(got)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
