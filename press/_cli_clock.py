"""``press date`` / ``press time`` — print the current date or time.

Modelled on GNU ``date``: an optional ``+FORMAT`` (strftime) and ``-u/--utc``.
Without ``+FORMAT`` the format comes from ``config.toml`` (``[date]`` /
``[time]``), so the CLI prints exactly what the daemon's hotkey inserts.
"""

from __future__ import annotations

import sys
from functools import partial
from typing import TYPE_CHECKING

from press._cli_helpers import report_error, write_clipboard_or_warn

if TYPE_CHECKING:
    import argparse

    from press._cli_helpers import _SubParsers

_HELP = {
    "date": "Print today's date (default: YYYYMMDD)",
    "time": "Print the current time (default: hhmmss)",
}


def _register_clock_command(sub: _SubParsers, name: str) -> None:
    """Register ``press date`` or ``press time`` (*name*)."""
    from press.commands import special_aliases

    p = sub.add_parser(name, aliases=special_aliases(name), help=_HELP[name])
    p.add_argument(
        "format",
        nargs="?",
        default=None,
        metavar="+FORMAT",
        help=(
            "strftime format overriding config.toml, as in GNU date "
            "(e.g. +%%Y-%%m-%%d for YYYY-MM-DD)"
        ),
    )
    p.add_argument("-u", "--utc", action="store_true", help="Use UTC instead of local time")
    p.add_argument(
        "-C",
        "--copy",
        action="store_true",
        help="Also copy the output to the clipboard",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress all stderr output")
    p.set_defaults(func=partial(_run_clock, name))


def _configured_format(name: str) -> str:
    """Return the ``[date]``/``[time]`` format from ``config.toml``.

    Imported here, not at module level: ``press.config`` pulls in tomllib and
    pathlib, which only this command (not every CLI start) should pay for.
    """
    from press.config import load_config

    config = load_config()
    return config.date.format if name == "date" else config.time.format


def _format_value(name: str, raw: str | None, *, utc: bool) -> str:
    """Format the current time from ``+FORMAT``, or from config.toml without it.

    Raises:
        ValueError: For a missing ``+``, an unusable format, or an unreadable
            ``config.toml`` (the message then names the key to fix).
    """
    from press import clock

    if raw is None:
        return clock.format_configured(name, _configured_format(name), utc=utc)
    if not raw.startswith("+"):
        raise ValueError(f"format must start with '+' (as in GNU date), got {raw!r}")
    return clock.format_now(raw[1:], utc=utc)


def _run_clock(name: str, a: argparse.Namespace) -> int:
    try:
        value = _format_value(name, a.format, utc=a.utc)
    except ValueError as exc:
        return report_error(name, exc, quiet=a.quiet)
    sys.stdout.write(value + "\n")
    sys.stdout.flush()
    if a.copy:
        from press._cli_helpers import _snapshot_clipboard_for_undo

        # Like uuid, stdout already delivered the value, so a clipboard
        # failure is a warning.  Unlike uuid, keep the overwritten text for
        # undo: a date lands on the clipboard often, by habit.
        _snapshot_clipboard_for_undo()
        write_clipboard_or_warn(value, cmd=name, quiet=a.quiet)
    return 0
