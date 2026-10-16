"""CLI registration for the ``notify`` command group.

``press notify off`` / ``on`` set the daemon's tray-notification switch
(:mod:`press._notify`).  Two explicit actions instead of a toggle: before a
screen share the user may run ``off`` more than once to be sure, and a toggle
would turn notifications back on.  The running daemon reads the switch before
every notification, so no restart is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

    from press._cli_helpers import _SubParsers


def _register_notify_commands(sub: _SubParsers) -> None:
    """Register the ``notify`` subcommand family."""
    notify_p = sub.add_parser(
        "notify",
        help="Turn the daemon's tray notifications off/on (e.g. for screen sharing)",
        description=(
            "Turn the daemon's tray notifications off or on.\n\n"
            "'press notify off' is not a toggle: running it again keeps\n"
            "notifications off. The running daemon applies it to the very next\n"
            "notification, no restart needed. From the daemon itself: the\n"
            "prefix chord, then Shift+M (off) or 'unmute' (on)."
        ),
    )
    notify_sub = notify_p.add_subparsers(dest="notify_action", metavar="ACTION")
    # print_help: shown when no ACTION is given (see _handle_notify).
    notify_p.set_defaults(func=_handle_notify, print_help=notify_p.print_help)

    notify_sub.add_parser("off", help="Stop showing tray notifications")
    notify_sub.add_parser("on", help="Show tray notifications again")
    notify_sub.add_parser("status", help="Show whether tray notifications are on")


def _handle_notify(args: argparse.Namespace) -> int:
    action: str | None = getattr(args, "notify_action", None)
    if action is None:
        args.print_help()
        return 0

    from press._notify import notifications_enabled, set_notifications_enabled

    match action:
        case "off":
            set_notifications_enabled(False)
        case "on":
            set_notifications_enabled(True)
        case "status":
            pass
        case _:
            return 1
    print(f"press notify: {'ON' if notifications_enabled() else 'OFF'}")
    return 0
