#!/usr/bin/env python3
"""
Text Expander Daemon for macOS Tahoe 26.
- Auto-reloads snippets.yaml within 2 seconds of any save
- Handles SIGUSR1 for instant reload (triggered by `snip add/remove/reload`)
- Writes PID file so the CLI can signal it
"""

import os
import sys
import signal
import time
import yaml
from pynput import keyboard

CONFIG_DIR  = os.path.expanduser("~/.config/textexpander")
CONFIG_PATH = os.path.join(CONFIG_DIR, "snippets.yaml")
PID_PATH    = os.path.join(CONFIG_DIR, "expander.pid")

# Mutable state shared between main() and on_press()
_state = {
    "snippets": {},
    "max_len":  10,
    "mtime":    0.0,
    "reload_requested": False,
}


# ── Snippet loading ────────────────────────────────────────────────────────────

def load_snippets(label="startup"):
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        with open(CONFIG_PATH) as f:
            data = yaml.safe_load(f) or {}
        snippets = data.get("snippets", {})
        # Normalise all values to strings
        snippets = {str(k): str(v) for k, v in snippets.items()}
        _state["snippets"] = snippets
        _state["max_len"]  = max((len(k) for k in snippets), default=10) + 2
        _state["mtime"]    = mtime
        print(f"[expander] {label}: {len(snippets)} snippet(s) loaded.", flush=True)
    except FileNotFoundError:
        print(f"[expander] {CONFIG_PATH} not found — starting with empty snippets.", flush=True)
    except Exception as e:
        print(f"[expander] Error loading snippets: {e}", file=sys.stderr, flush=True)


def check_mtime_reload():
    """Called from the keypress loop every ~2 s. Returns immediately if unchanged."""
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if mtime != _state["mtime"]:
            load_snippets(label="file-changed reload")
    except Exception:
        pass


# ── Signal / PID helpers ───────────────────────────────────────────────────────

def handle_sigusr1(signum, frame):
    """Marks a reload as requested; the keypress loop picks it up safely."""
    _state["reload_requested"] = True


def write_pid():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))


def remove_pid():
    try:
        os.remove(PID_PATH)
    except Exception:
        pass


# ── Expansion logic ────────────────────────────────────────────────────────────

def type_expansion(ctrl, expansion):
    """Types multi-line expansions correctly (YAML \n → Enter key)."""
    lines = expansion.split("\n")
    for i, line in enumerate(lines):
        ctrl.type(line)
        if i < len(lines) - 1:
            ctrl.press(keyboard.Key.enter)
            ctrl.release(keyboard.Key.enter)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    import atexit

    write_pid()
    atexit.register(remove_pid)
    signal.signal(signal.SIGUSR1, handle_sigusr1)

    load_snippets()

    buffer      = []
    ctrl        = keyboard.Controller()
    last_check  = time.time()

    def on_press(key):
        nonlocal last_check

        # ── Periodic & signal-triggered reloads ──────────────────────────────
        now = time.time()
        if _state["reload_requested"]:
            load_snippets(label="SIGUSR1 reload")
            _state["reload_requested"] = False
            last_check = now
        elif now - last_check >= 2.0:
            check_mtime_reload()
            last_check = now

        # ── Buffer management ─────────────────────────────────────────────────
        try:
            char = key.char
        except AttributeError:
            # Navigation / modifier keys break word context → clear buffer
            if key not in (
                keyboard.Key.shift,   keyboard.Key.shift_r,
                keyboard.Key.caps_lock,
                keyboard.Key.alt,     keyboard.Key.alt_r,
                keyboard.Key.ctrl,    keyboard.Key.ctrl_r,
                keyboard.Key.cmd,     keyboard.Key.cmd_r,
            ):
                buffer.clear()
            return

        # key.char can be None for some keys (e.g. numbers under modifier states)
        if char is None:
            return

        buffer.append(char)
        if len(buffer) > _state["max_len"]:
            del buffer[0]

        # ── Trigger matching ──────────────────────────────────────────────────
        current = "".join(buffer)
        for trigger, expansion in _state["snippets"].items():
            if current.endswith(trigger):
                buffer.clear()
                for _ in range(len(trigger)):
                    ctrl.press(keyboard.Key.backspace)
                    ctrl.release(keyboard.Key.backspace)
                type_expansion(ctrl, expansion)
                return

    print(
        f"[expander] Running (PID {os.getpid()})\n"
        f"[expander] Watching: {CONFIG_PATH}\n"
        f"[expander] Ctrl+C to stop.",
        flush=True,
    )

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
