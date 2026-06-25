#!/usr/bin/env python3
"""
snip — CLI for managing text expansion snippets.

Commands:
  snip list                      List all snippets in a table
  snip add <trigger> <text>      Add or update a snippet
  snip remove <trigger>          Remove a snippet
  snip reload                    Hot-reload the running daemon instantly
  snip status                    Show daemon status and snippet count

Examples:
  snip add ";;em"  "you@example.com"
  snip add ";;sig" $'Best regards,\\nYour Name'
  snip remove ";;em"
  snip list
  snip reload
"""

import os
import sys
import signal
import argparse
import yaml

CONFIG_DIR  = os.path.expanduser("~/.config/textexpander")
CONFIG_PATH = os.path.join(CONFIG_DIR, "snippets.yaml")
PID_PATH    = os.path.join(CONFIG_DIR, "expander.pid")

BOLD  = "\033[1m"
DIM   = "\033[2m"
GREEN = "\033[32m"
RED   = "\033[31m"
RESET = "\033[0m"


# ── YAML helpers ───────────────────────────────────────────────────────────────

def load_yaml():
    if not os.path.exists(CONFIG_PATH):
        return {"snippets": {}}
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("snippets", {})
    return data


def save_yaml(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False,
                  allow_unicode=True, sort_keys=True)


# ── Daemon helpers ─────────────────────────────────────────────────────────────

def get_daemon_pid():
    """Returns the daemon PID if it is running, else None."""
    try:
        with open(PID_PATH) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)   # probe — raises if dead
        return pid
    except Exception:
        return None


def signal_daemon():
    pid = get_daemon_pid()
    if pid:
        os.kill(pid, signal.SIGUSR1)
        return pid
    return None


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_list(args):
    data = load_yaml()
    snippets = data.get("snippets", {})
    if not snippets:
        print(f"{DIM}No snippets yet.{RESET}  Try: snip add ;;trigger 'your text'")
        return

    tw = max(len(t) for t in snippets)
    tw = max(tw, 7)   # minimum "TRIGGER" header width

    header     = f"{BOLD}{'TRIGGER':<{tw}}   EXPANSION{RESET}"
    separator  = f"{DIM}{'─' * (tw + 3 + 55)}{RESET}"

    print(header)
    print(separator)
    for trigger in sorted(snippets):
        expansion = str(snippets[trigger])
        display   = expansion.replace("\n", f"{DIM}↵{RESET} ")
        if len(expansion) > 60:
            display = expansion[:57].replace("\n", "↵ ") + "…"
        print(f"{GREEN}{trigger:<{tw}}{RESET}   {display}")

    print(separator)
    print(f"{DIM}{len(snippets)} snippet(s){RESET}")


def cmd_add(args):
    data    = load_yaml()
    trigger = args.trigger
    # Join expansion words in case the user didn't quote it
    expansion = " ".join(args.expansion) if isinstance(args.expansion, list) \
                else args.expansion

    verb = "Updated" if trigger in data["snippets"] else "Added"
    data["snippets"][trigger] = expansion
    save_yaml(data)

    display = expansion.replace("\n", "↵ ")
    print(f"{GREEN}✓{RESET} {verb}: {BOLD}{trigger}{RESET} → {display}")

    pid = signal_daemon()
    if pid:
        print(f"{DIM}Daemon reloaded (PID {pid}).{RESET}")
    else:
        print(f"{DIM}Daemon not running — changes will apply on next start.{RESET}")


def cmd_remove(args):
    data    = load_yaml()
    trigger = args.trigger

    if trigger not in data["snippets"]:
        print(f"{RED}✗{RESET} Trigger {BOLD}{trigger}{RESET} not found.")
        cmd_list(args)
        sys.exit(1)

    del data["snippets"][trigger]
    save_yaml(data)
    print(f"{GREEN}✓{RESET} Removed: {BOLD}{trigger}{RESET}")

    pid = signal_daemon()
    if pid:
        print(f"{DIM}Daemon reloaded (PID {pid}).{RESET}")


def cmd_reload(args):
    pid = signal_daemon()
    if pid:
        print(f"{GREEN}✓{RESET} Reload signal sent to daemon (PID {pid}).")
    else:
        print(f"{RED}✗{RESET} Daemon is not running.")
        print(f"  Start it with:  python3 {CONFIG_DIR}/expander.py &")
        sys.exit(1)


def cmd_status(args):
    pid = get_daemon_pid()
    if pid:
        data  = load_yaml()
        count = len(data.get("snippets", {}))
        print(f"{GREEN}●{RESET} Running  (PID {pid})")
        print(f"  Config : {CONFIG_PATH}")
        print(f"  Loaded : {count} snippet(s)")
    else:
        print(f"{RED}○{RESET} Not running")
        print(f"  Start with:  python3 {CONFIG_DIR}/expander.py &")


# ── Argument parser ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="snip",
        description="Manage text expansion snippets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    sub.add_parser("list",   help="List all snippets")

    p_add = sub.add_parser("add", help="Add or update a snippet")
    p_add.add_argument("trigger",   help="Trigger string, e.g. ;;em")
    p_add.add_argument("expansion", help="Expansion text", nargs="+")

    p_rm = sub.add_parser("remove", help="Remove a snippet")
    p_rm.add_argument("trigger", help="Trigger to remove")

    sub.add_parser("reload", help="Hot-reload the running daemon")
    sub.add_parser("status", help="Show daemon status")

    args = parser.parse_args()

    dispatch = {
        "list":   cmd_list,
        "add":    cmd_add,
        "remove": cmd_remove,
        "reload": cmd_reload,
        "status": cmd_status,
    }

    if args.command not in dispatch:
        parser.print_help()
        sys.exit(0)

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
