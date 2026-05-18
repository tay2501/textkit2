"""CLI registration for the ``daemon`` command group."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from press._cli_helpers import _SubParsers


def _lines_type(val: str) -> int | None:
    """Argparse type for --lines: accept a positive integer or the string 'all'."""
    if val.lower() == "all":
        return None
    try:
        n = int(val)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid value for --lines: {val!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError("--lines must be a positive integer or 'all'")
    return n


def _register_daemon_commands(sub: _SubParsers) -> None:
    daemon_p = sub.add_parser("daemon", help="Manage press background daemon")
    daemon_sub = daemon_p.add_subparsers(dest="daemon_action", metavar="ACTION")
    daemon_p.set_defaults(func=_handle_daemon)

    daemon_sub.add_parser("start", help="Start the tray icon + hotkey daemon")
    daemon_sub.add_parser("stop", help="Stop the running daemon")
    daemon_sub.add_parser("restart", help="Stop and restart the daemon")

    p_status = daemon_sub.add_parser("status", help="Show running status")
    p_status.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output as JSON",
    )

    p_logs = daemon_sub.add_parser(
        "logs",
        help="Show daemon log entries",
        description=(
            "Display entries from the daemon log file.\n\n"
            "Default: last 50 lines, human-readable.\n"
            "Use --follow to stream new entries (Ctrl+C to stop).\n"
            "Use --json to output as NDJSON (one JSON object per line)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_logs.add_argument(
        "-f",
        "--follow",
        action="store_true",
        help="Stream new entries until Ctrl+C",
    )
    p_logs.add_argument(
        "-n",
        "--lines",
        type=_lines_type,
        default=50,
        metavar="N",
        help="Lines to show (positive integer or 'all'; default: 50)",
    )
    p_logs.add_argument(
        "--level",
        choices=["debug", "info", "warning", "error", "all"],
        default="all",
        metavar="LEVEL",
        help="Minimum log level: debug, info, warning, error, all (default: all)",
    )
    p_logs.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output as NDJSON (one JSON object per line)",
    )


def _handle_daemon(args: argparse.Namespace) -> int:
    action = getattr(args, "daemon_action", None)
    if action is None:
        import subprocess

        subprocess.run([sys.argv[0], "daemon", "--help"], check=False)
        return 0
    match action:
        case "start":
            from press.daemon import run_daemon

            run_daemon()
            return 0
        case "stop":
            from press.daemon import stop_daemon

            return stop_daemon()
        case "status":
            from press.daemon import daemon_status

            return daemon_status(as_json=getattr(args, "as_json", False))
        case "restart":
            from press.daemon import run_daemon, stop_daemon

            stop_daemon()
            run_daemon()
            return 0
        case "logs":
            from press.daemon import daemon_logs

            return daemon_logs(
                lines=args.lines,
                follow=args.follow,
                level=args.level,
                as_json=args.as_json,
            )
        case _:
            return 1
