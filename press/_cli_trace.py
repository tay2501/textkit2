"""CLI registration for the ``trace`` command group.

Flips a marker file (``%APPDATA%\\press\\trace``) on and off so diagnostic
DEBUG-level timing logs (:func:`press.daemon._logs.timed`) can be enabled on
an unfamiliar PC without a config.toml edit or a daemon restart — the daemon
re-checks the marker once per dispatched action
(:func:`press.daemon._logs.refresh_level`).
"""

from __future__ import annotations

import contextlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

    from press._cli_helpers import _SubParsers


def _register_trace_commands(sub: _SubParsers) -> None:
    """Register the ``trace`` subcommand family."""
    trace_p = sub.add_parser(
        "trace",
        help="Toggle diagnostic trace logging (for diagnosing slow PCs)",
        description=(
            "Toggle diagnostic DEBUG-level timing logs.\n\n"
            "'press trace on' creates a marker file; the running daemon picks it\n"
            "up on the next dispatched action (no restart needed), and future\n"
            "CLI-standalone invocations print timing to stderr.\n"
            "'press trace off' removes the marker; 'press trace status' reports\n"
            "the current state."
        ),
    )
    trace_sub = trace_p.add_subparsers(dest="trace_action", metavar="ACTION")
    trace_p.set_defaults(func=_handle_trace)

    trace_sub.add_parser("on", help="Enable diagnostic trace logging")
    trace_sub.add_parser("off", help="Disable diagnostic trace logging")
    trace_sub.add_parser("status", help="Show whether diagnostic trace logging is enabled")


def _handle_trace(args: argparse.Namespace) -> int:
    action: str | None = getattr(args, "trace_action", None)
    if action is None:
        import subprocess

        subprocess.run([sys.argv[0], "trace", "--help"], check=False)
        return 0

    from press._paths import press_dir, trace_path

    match action:
        case "on":
            path = trace_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            log_path = press_dir() / "daemon.log"
            print(f"press trace: ON — daemon logs: {log_path}")
            print("press trace: CLI-standalone runs will also print timing to stderr")
            return 0
        case "off":
            with contextlib.suppress(FileNotFoundError):
                trace_path().unlink()
            print("press trace: OFF")
            return 0
        case "status":
            state = "ON" if trace_path().exists() else "OFF"
            print(f"press trace: {state}")
            return 0
        case _:
            return 1
