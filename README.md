# TextExpander — Lightweight DIY Text Expansion for macOS

A privacy-first, zero-subscription text expander for macOS. Monitors keystrokes
locally, expands trigger shortcuts into full text snippets system-wide, and is
fully controlled from the Terminal. No cloud sync, no telemetry, no licence fees.

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements](#requirements)
3. [File Structure](#file-structure)
4. [Installation](#installation)
5. [Configuration — snippets.yaml](#configuration)
6. [CLI Reference — snip](#cli-reference)
7. [Running the Daemon](#running-the-daemon)
8. [Auto-start on Login](#auto-start-on-login)
9. [Version History](#version-history)
10. [Debugging Guide](#debugging-guide)
11. [Known Issues & Limitations](#known-issues--limitations)

---

## Overview

The tool is composed of three components:

| File | Role |
|---|---|
| `expander.py` | Daemon — monitors keyboard, expands triggers |
| `snip.py` | CLI — manages snippets from the Terminal |
| `snippets.yaml` | Config — your triggers and their expansions |

**How expansion works:** the daemon keeps a rolling buffer of the last N
characters typed. When the buffer tail matches a trigger defined in
`snippets.yaml`, it erases the trigger with backspaces and types the expansion.
Everything runs locally in memory; nothing is written to disk except the
snippets file you manage yourself.

**Trigger convention:** this installation uses `!!` as the prefix (e.g. `!!em`,
`!!sig`). The prefix is not enforced by the code — it is just a YAML key
convention to avoid accidental matches. You can change it at any time by
editing `snippets.yaml`.

---

## Requirements

### macOS

- **macOS Tahoe 26.5.1** (tested). Should work on Sequoia 15.x and later.
- Two Privacy permissions must be granted to Python:
  - **Accessibility** — System Settings → Privacy & Security → Accessibility
  - **Input Monitoring** — System Settings → Privacy & Security → Input Monitoring

### Python

- **Python 3.14** (current runtime — uv-managed venv at
  `~/.config/textexpander/.venv`).
- **Python 3.10 or later** is the minimum supported version.
  - Python 3.9 (Xcode CLT) works but is no longer used — see Version History
    for why it was replaced.

Check the active runtime:
```bash
~/.config/textexpander/.venv/bin/python --version
```

### Python packages

| Package | Version | Purpose |
|---|---|---|
| `pynput` | ≥ 1.7 | Keyboard monitoring and injection |
| `pyyaml` | ≥ 6.0 | Parsing `snippets.yaml` |

Install:
```bash
uv venv ~/.config/textexpander/.venv --python 3.14
uv pip install pynput pyyaml --python ~/.config/textexpander/.venv/bin/python
```

If uv is not installed, install it via Homebrew:
```bash
brew install uv
```

> **Legacy install (not recommended):** `pip3 install pynput pyyaml --user`
> installs into the global Python 3.9 CLT environment, which has known
> stability issues on Tahoe 26. Use uv.

---

## File Structure

After installation, all runtime files live under `~/.config/textexpander/`:

```
~/.config/textexpander/
├── expander.py       # Daemon — do not edit unless updating
├── snip.py           # CLI tool — do not edit unless updating
├── snippets.yaml     # YOUR snippets — edit freely, daemon auto-reloads
└── expander.log      # Runtime log — check here when debugging
```

The LaunchAgent plist that starts the daemon at login lives at:
```
~/Library/LaunchAgents/local.textexpander.plist
```

The `snip` command is symlinked to:
```
~/.local/bin/snip → ~/.config/textexpander/snip.py
```

---

## Installation

### Fresh install

1. Download all four source files into one folder:
   - `expander.py`
   - `snip.py`
   - `snippets.yaml`
   - `install.sh`

2. Ensure uv is available (it manages the Python runtime):
   ```bash
   brew install uv   # skip if already installed
   which uv          # should return /opt/homebrew/bin/uv
   ```

3. Run the installer:
   ```bash
   bash install.sh
   ```
   The installer will:
   - Detect Homebrew vs system Python and use the best available
   - Install `pynput` and `pyyaml`
   - Copy scripts to `~/.config/textexpander/`
   - Create starter `snippets.yaml` (skipped if file already exists)
   - Create `~/.local/bin/snip` symlink
   - Add `~/.local/bin` to `$PATH` in `~/.zshrc`
   - Create `start.sh` for Login Item auto-start
   - Launch the daemon and prompt for Accessibility permission

4. Grant both Privacy permissions when prompted (see Requirements above).

5. Create and load the LaunchAgent for silent background auto-start:
   ```bash
   cat > ~/Library/LaunchAgents/local.textexpander.plist << EOF
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
       "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>local.textexpander</string>

       <key>ProgramArguments</key>
       <array>
           <string>$HOME/.config/textexpander/.venv/bin/python</string>
           <string>$HOME/.config/textexpander/expander.py</string>
       </array>

       <key>KeepAlive</key>
       <true/>
       <key>RunAtLoad</key>
       <true/>
       <key>ThrottleInterval</key>
       <integer>5</integer>

       <!-- Required for Input Monitoring / Accessibility APIs -->
       <key>ProcessType</key>
       <string>Interactive</string>

       <key>StandardOutPath</key>
       <string>$HOME/.config/textexpander/expander.log</string>
       <key>StandardErrorPath</key>
       <string>$HOME/.config/textexpander/expander.log</string>
   </dict>
   </plist>
   EOF

   launchctl bootstrap gui/$(id -u) \
       ~/Library/LaunchAgents/local.textexpander.plist
   ```
   No Login Item or Terminal window needed — the daemon runs silently in the
   background and restarts automatically on crash.

   > **Note:** the venv path is stable — it does not change when uv installs
   > new Python versions. Only update `ProgramArguments` if you deliberately
   > recreate the venv at a different path.

### Re-install / update

To update the daemon or CLI without touching your snippets:
```bash
cp expander.py ~/.config/textexpander/expander.py
cp snip.py     ~/.config/textexpander/snip.py
launchctl kickstart -k gui/$(id -u)/local.textexpander
```

To recreate the venv from scratch (e.g. after wiping `~/.config/textexpander/`):
```bash
uv venv ~/.config/textexpander/.venv --python 3.14
uv pip install pynput pyyaml --python ~/.config/textexpander/.venv/bin/python
```

`snippets.yaml` is never overwritten by the installer or any update step.

---

## Configuration

### snippets.yaml format

```yaml
snippets:
  "!!trigger":  "Single-line expansion"

  "!!multiline": |
    Line one
    Line two
    Line three

  "!!inline-newline": "Line one\nLine two"
```

**Rules:**
- Always quote trigger keys with double quotes. The `!!` prefix is a YAML
  type-tag character and will break parsing if unquoted.
- Prefer the `|` block scalar for multi-line values — it is the most readable.
- Long single-paragraph expansions can use `>-` (folds line breaks to spaces,
  strips trailing newline):
  ```yaml
  "!!long": >-
    This is a long paragraph that wraps in the file
    but will be typed as a single line of text.
  ```

### Editing snippets

**Option A — edit the file directly** (auto-reloads within 2 seconds):
```bash
open ~/.config/textexpander/snippets.yaml
# or
code ~/.config/textexpander/snippets.yaml
```

**Option B — use the CLI** (instant reload via signal):
```bash
snip add '!!trigger' 'expansion text'
snip remove '!!trigger'
```

Never edit the copy in your Downloads folder — the daemon reads only from
`~/.config/textexpander/snippets.yaml`.

---

## CLI Reference

All commands operate on `~/.config/textexpander/snippets.yaml` and
automatically signal the daemon to reload.

```
snip list                     List all snippets in a formatted table
snip add <trigger> <text>     Add or update a snippet
snip remove <trigger>         Remove a snippet
snip reload                   Send instant reload signal to running daemon
snip status                   Show daemon PID and snippet count
```

### Examples

```bash
snip add '!!em'   'you@example.com'
snip add '!!sig'  $'Best regards,\nYour Name'   # $'...' interprets \n in bash
snip remove '!!old'
snip list
snip status
```

**Shell quoting rule:** always single-quote triggers containing `!!` to prevent
bash from interpreting them as history expansion (`!!` = last command).

---

## Running the Daemon

The daemon is managed by launchd. Use `launchctl` for all lifecycle operations.

### Start

```bash
launchctl bootstrap gui/$(id -u) \
    ~/Library/LaunchAgents/local.textexpander.plist
```

### Stop

```bash
launchctl bootout gui/$(id -u)/local.textexpander
```

### Restart

```bash
launchctl kickstart -k gui/$(id -u)/local.textexpander
```

### Check status

```bash
snip status                                           # shows PID and snippet count
launchctl list | grep textexpander                    # shows PID and last exit code
tail -f ~/.config/textexpander/expander.log           # live log output
```

A healthy `launchctl list` line looks like:
```
920    0    local.textexpander
^^^    ^
PID    exit code (0 = clean)
```

A `-` in the PID column means launchd's instance is not running — check the
log for the cause.

> **Note:** `pkill -f expander.py` still kills the process, but because
> `KeepAlive: true` is set in the plist, launchd will restart it after ~5
> seconds. Use `launchctl bootout` to stop it permanently.

---

## Auto-start on Login

The daemon is managed by a launchd **LaunchAgent** — the proper macOS
mechanism for silent background services. It starts automatically at login,
runs with no Terminal window, and restarts automatically on crash.

The plist lives at:
```
~/Library/LaunchAgents/local.textexpander.plist
```

**To verify it is loaded:**
```bash
launchctl list | grep textexpander
# Expected: <PID>   0   local.textexpander
```

**To reload after editing the plist:**
```bash
launchctl bootout gui/$(id -u)/local.textexpander
launchctl bootstrap gui/$(id -u) \
    ~/Library/LaunchAgents/local.textexpander.plist
```

**If the daemon stops starting after a macOS update:**

macOS occasionally invalidates LaunchAgent registrations after major updates.
Re-load with:
```bash
launchctl bootstrap gui/$(id -u) \
    ~/Library/LaunchAgents/local.textexpander.plist
```

If that returns an error saying the service is already loaded, bootout first:
```bash
launchctl bootout gui/$(id -u)/local.textexpander 2>/dev/null
launchctl bootstrap gui/$(id -u) \
    ~/Library/LaunchAgents/local.textexpander.plist
```

**If you switch Python versions** (e.g. after installing Homebrew Python),
update the `ProgramArguments` path in the plist and reload:
```bash
# Edit the path:
nano ~/Library/LaunchAgents/local.textexpander.plist
# Then reload:
launchctl bootout gui/$(id -u)/local.textexpander
launchctl bootstrap gui/$(id -u) \
    ~/Library/LaunchAgents/local.textexpander.plist
```

---

## Version History

### v1.5 — June 2026
- Migrated Python runtime from Xcode CLT shim (`/usr/bin/python3`, 3.9) to a
  **uv-managed isolated venv** (`~/.config/textexpander/.venv`, Python 3.14).
  - Eliminates the CLT shim's Input Monitoring permission instability.
  - Consistent with the uv-based Python tooling already in use on this machine.
  - Venv path (`~/.config/textexpander/.venv/bin/python`) is stable across
    uv and Python version changes.
  - LaunchAgent plist `ProgramArguments` updated to point at venv binary.
  - Input Monitoring entry for Python 3.9 (CLT) removed from System Settings.

### v1.4 — June 2026
- Replaced `start.sh` Login Item with a launchd **LaunchAgent**
  (`~/Library/LaunchAgents/local.textexpander.plist`).
  - Daemon now starts silently at login with no Terminal window.
  - `KeepAlive: true` provides automatic restart on crash.
  - `ProcessType: Interactive` required for Input Monitoring / Accessibility
    APIs to function correctly under launchd.
  - `ThrottleInterval: 5` replaces the `sleep 5` in the former `start.sh`.
- Documented that `/usr/bin/python3` (Xcode CLT shim) does not trigger the
  Input Monitoring permission dialog automatically. Workaround: manually add
  the underlying CLT binary to Input Monitoring via System Settings → `+`.
  See [Debugging Guide](#input-monitoring-not-appearing-in-system-settings).

### v1.3 — June 2026
- Fixed `TypeError: sequence item 0: expected str instance, NoneType found`
  crash when typing keys whose `pynput` `.char` attribute returns `None`
  (e.g. numbers pressed under certain modifier states such as `!1`).
- Guard added: `if char is None: return` before appending to buffer.

### v1.2 — June 2026
- Fixed `install.sh` pip flag incompatibility: replaced `--break-system-packages`
  (requires pip ≥ 23) with `--user`, compatible with all pip versions.
- Added Homebrew Python auto-detection in `install.sh`; prefers
  `/opt/homebrew/bin/python3` over Xcode CLT Python to avoid `pyobjc-core`
  compilation failure on Tahoe 26 (Clang `-Wdefault-const-init-var-unsafe`).
- pip upgrade step added as fallback for CLT Python environments.

### v1.1 — June 2026
- Added hot-reload on file save: daemon polls `snippets.yaml` mtime every 2
  seconds; no restart needed after editing.
- Added SIGUSR1 handler: `snip add/remove/reload` signals the daemon for
  instant reload (bypasses the 2-second poll).
- Added PID file (`expander.pid`) so the CLI can locate and signal the daemon.
- `snip` CLI released with `list`, `add`, `remove`, `reload`, `status` commands.
- `snip add/remove` auto-signals daemon after saving.

### v1.0 — June 2026
- Initial release.
- System-wide keyboard monitoring via `pynput`.
- YAML-based snippet configuration.
- Trigger prefix `!!` adopted (YAML keys must be quoted).
- Rolling character buffer with configurable max length.
- Multi-line expansion support via `\n` split and Enter key injection.
- Special-key buffer-clear logic (navigation, cmd, ctrl, etc.).
- Login Item auto-start via `start.sh`.
- `nohup` + `disown` launch pattern for silent background operation.

---

## Debugging Guide

### Daemon not running after reboot

```bash
snip status        # confirms it is not running
# Check the log for startup errors:
cat ~/.config/textexpander/expander.log
# Restart via launchd:
launchctl bootout gui/$(id -u)/local.textexpander 2>/dev/null
launchctl bootstrap gui/$(id -u) \
    ~/Library/LaunchAgents/local.textexpander.plist
```

If it fails at every reboot, verify the plist is still present:
```bash
ls ~/Library/LaunchAgents/local.textexpander.plist
```
If missing, recreate it following the Installation section above.
macOS occasionally removes LaunchAgents after major system updates.

### Triggers not expanding (daemon is running)

1. Check both Privacy permissions:
   - System Settings → Privacy & Security → **Accessibility** → Python ✅
   - System Settings → Privacy & Security → **Input Monitoring** → Python ✅

   If Input Monitoring does not show a Python entry at all, see
   [Input Monitoring not appearing in System Settings](#input-monitoring-not-appearing-in-system-settings) below.

2. Test that pynput can see keystrokes at all:
   ```bash
   python3 -c "
   from pynput import keyboard
   def show(k):
       try: print(k.char, end='', flush=True)
       except: print(f'[{k}]', end='', flush=True)
   with keyboard.Listener(on_press=show) as l:
       l.join()
   "
   ```
   Type a few characters. If nothing prints → Input Monitoring is blocked.
   If characters appear doubled → two instances of the daemon are running
   (check `snip status` and kill the duplicate with `pkill -f expander.py`).
   `Ctrl+C` to stop the test.

3. Verify the daemon is reading your snippets file:
   ```bash
   snip status      # should show correct snippet count
   snip list        # triggers should show !! prefix, not ;;
   ```
   If `snip list` shows old `;;` snippets, the daemon is reading a stale copy.
   Confirm the file path:
   ```bash
   ls -la ~/.config/textexpander/snippets.yaml
   ```

### Secure Input locking (expansions stop working mid-session)

macOS Secure Input blocks all keyboard accessibility when a sensitive field
is active (password fields, some password manager popups). It sometimes gets
stuck even after leaving those fields.

Fix:
```bash
launchctl kickstart -k gui/$(id -u)/local.textexpander
# Close and reopen your password manager / browser if it persists
```

### pyobjc-core compilation failure (pip install fails)

Symptom: `error: command '/usr/bin/clang' failed` with
`-Wdefault-const-init-var-unsafe` errors during `pip install pynput`.

Cause: Xcode CLT Python (3.9) with pip 21.x has no pre-built wheels for
`pyobjc-core` and falls back to compilation; Tahoe 26's Clang rejects the
older C code.

Fix:
```bash
# Definitive fix — use uv-managed venv (current setup)
uv venv ~/.config/textexpander/.venv --python 3.14
uv pip install pynput pyyaml --python ~/.config/textexpander/.venv/bin/python
# Then reload the LaunchAgent (see Auto-start on Login)

# Legacy workaround — upgrade pip (only if still using system Python ≥ 3.10)
python3 -m pip install --upgrade pip --user
pip3 install pynput pyyaml --user
```

### Input Monitoring not appearing in System Settings

When the daemon is launched via launchd (rather than interactively from
Terminal), macOS may never show the Input Monitoring permission dialog, and
`/usr/bin/python3` may not appear in the Input Monitoring list at all.

This happens because `/usr/bin/python3` is an Xcode CLT shim — it delegates
to the actual versioned binary and macOS does not always register the shim
as a permission target.

**Fix — manually add the underlying CLT binary:**

1. Stop the launchd daemon:
   ```bash
   launchctl bootout gui/$(id -u)/local.textexpander
   ```

2. Run the expander manually from Terminal (this runs in your GUI session
   and may trigger the permission dialog):
   ```bash
   python3 ~/.config/textexpander/expander.py
   ```

3. If no dialog appears, manually add the binary in System Settings:
   ```
   System Settings → Privacy & Security → Input Monitoring → +
   ```
   Press `Cmd+Shift+G` in the file picker and paste:
   ```
   /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9
   ```
   Toggle it on.

4. `Ctrl+C` the manual run, then restart via launchd:
   ```bash
   launchctl bootstrap gui/$(id -u) \
       ~/Library/LaunchAgents/local.textexpander.plist
   ```

> **Long-term fix:** install Homebrew Python (`brew install python3`). It is
> a proper standalone binary that holds Privacy permissions cleanly and avoids
> this issue entirely. Update `ProgramArguments` in the plist afterwards.

### snip command not found after install

```bash
source ~/.zshrc           # reload PATH in current terminal
# or open a new terminal window
which snip                # should return ~/.local/bin/snip
```

If still not found:
```bash
ls -la ~/.local/bin/snip  # check the symlink exists
echo $PATH                # check ~/.local/bin is present
```

### TypeError: sequence item 0: expected str instance, NoneType found

This crash occurred in v1.0–v1.2 when typing keys whose `pynput` `.char`
attribute returns `None` (e.g. the `1` key typed as `!1` via Shift).
Fixed in v1.3 — update `expander.py` and restart the daemon.

---

## Known Issues & Limitations

| Issue | Status | Workaround |
|---|---|---|
| Secure Input locking (password manager popups freeze expansion) | macOS design, not fixable | Restart daemon: `launchctl kickstart -k gui/$(id -u)/local.textexpander` |
| Does not expand inside password fields | macOS Secure Input intentional | By design — correct security behaviour |
| Expansions in some Electron apps (older versions) may miss first character | pynput timing | Add a short `time.sleep(0.05)` before `ctrl.type()` in `expander.py` if needed |
| macOS may revoke Input Monitoring permission after a major OS update | macOS behaviour | Re-grant in System Settings; if entry missing, re-add venv python binary manually |
| LaunchAgent may need reloading after a major macOS update | macOS behaviour | Run `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.textexpander.plist` |
| Python 3.9 (Xcode CLT) has no pre-built pyobjc wheels | Upstream — no longer relevant | Current setup uses uv-managed Python 3.14 |
