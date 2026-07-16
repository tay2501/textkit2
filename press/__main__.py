"""Command-line entry point for press."""

from __future__ import annotations

import argparse
import contextlib
import locale
import os
import sys
from typing import TYPE_CHECKING, Any, override

from press._cli_helpers import (
    _add_io_args,
    _run_transform,
    _SubParsers,
    bounded_int,
    write_clipboard_or_warn,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from press.commands import CliArg, ParametricCommand, SimpleCommand


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("press")
    except PackageNotFoundError:
        return "unknown"


class _LazyVersionAction(argparse.Action):
    """``--version`` action that defers the version lookup to invocation time.

    argparse's built-in ``version`` action needs the version string while the
    parser is being *built*, which would import ``importlib.metadata`` (and
    its email/urllib dependency chain, plus a site-packages dist-info scan)
    on every CLI startup.  Endpoint security agents amplify that file I/O,
    so the lookup runs only when ``--version`` is actually requested.
    """

    @override
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        print(f"press {_version()}")
        parser.exit()


# ---------------------------------------------------------------------------
# Transform command registration (simple and parametric)
# ---------------------------------------------------------------------------


def _register_transform_command(sub: _SubParsers, cmd: SimpleCommand | ParametricCommand) -> None:
    """Register one transform command from the central registry.

    Simple commands take no options beyond the standard I/O flags; parametric
    commands additionally get options generated from ``cmd.cli_args``, where
    each option's ``kwarg`` is both the argparse dest and the keyword argument
    forwarded to the transform function.
    """
    from press.commands import ParametricCommand

    cli_args = cmd.cli_args if isinstance(cmd, ParametricCommand) else ()
    p = sub.add_parser(cmd.name, aliases=list(cmd.aliases), help=cmd.help)
    _add_io_args(p)
    for arg in cli_args:
        kwargs: dict[str, Any] = {"dest": arg.kwarg, "help": arg.help}
        if arg.action is not None:
            kwargs["action"] = arg.action
        else:
            kwargs["default"] = arg.default
            if arg.type is not None:
                kwargs["type"] = arg.type
            if arg.metavar is not None:
                kwargs["metavar"] = arg.metavar
        p.add_argument(*arg.flags, **kwargs)

    # Bind cmd/cli_args as default arguments to avoid the loop late-binding pitfall.
    def _handler(
        a: argparse.Namespace,
        _cmd: SimpleCommand | ParametricCommand = cmd,
        _cli_args: tuple[CliArg, ...] = cli_args,
    ) -> int:
        def _apply(text: str, **kw: Any) -> str:
            # A running daemon already has the transform module in memory.
            # Delegating skips importing it here — the file opens that
            # endpoint security agents make expensive.
            from press._pipe import try_delegate

            delegated = try_delegate(_cmd.name, text, kw)
            if delegated is not None:
                return delegated
            from press.commands import run_command

            return run_command(_cmd.name, text, cli_kwargs=kw)

        extras = {arg.kwarg: getattr(a, arg.kwarg) for arg in _cli_args}
        return _run_transform(_apply, a, **extras)

    p.set_defaults(func=_handler)


def _genpass_clear_after(seconds: int, *, quiet: bool) -> None:
    """Wait *seconds*, then clear the clipboard unless another app overwrote it.

    KeePassXC-cli style conditional auto-clear: the sequence number is
    captured now (right after the password write) and the clipboard is only
    wiped if it is still unchanged after the delay.
    """
    import time

    from press.clipboard import clear_clipboard_if_unchanged, get_clipboard_sequence_number

    try:
        sequence = get_clipboard_sequence_number()
        if not quiet:
            print(f"press genpass: clearing clipboard in {seconds}s ...", file=sys.stderr)
        time.sleep(seconds)
        if not clear_clipboard_if_unchanged(sequence):
            if not quiet:
                print(
                    "press genpass: clipboard changed by another app — not cleared",
                    file=sys.stderr,
                )
        elif not quiet:
            print("press genpass: clipboard cleared", file=sys.stderr)
    except (RuntimeError, OSError) as exc:
        if not quiet:
            print(f"press genpass: warning: clipboard clear failed: {exc}", file=sys.stderr)


def _register_genpass_command(sub: _SubParsers) -> None:
    p = sub.add_parser("genpass", aliases=["gp"], help="Generate a secure random password")
    p.add_argument(
        "-n",
        "--length",
        type=bounded_int(1, "length"),
        default=20,
        metavar="N",
        help="Password length (default: 20)",
    )
    p.add_argument(
        "-s",
        "--symbols",
        action="store_true",
        help="Include ASCII punctuation characters",
    )
    p.add_argument("-C", "--clip-out", action="store_true", help="Write output to clipboard")
    p.add_argument(
        "-N",
        "--no-clip",
        action="store_true",
        help="Do NOT write to clipboard even on a TTY (prevents accidental overwrite)",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress all stderr output")
    p.add_argument(
        "--clear-after",
        type=bounded_int(0, "seconds"),
        default=0,
        metavar="SEC",
        help=(
            "Clear the clipboard after SEC seconds if it still holds the "
            "password (0 = disabled; KeePassXC defaults to 12)"
        ),
    )

    def _gp(a: argparse.Namespace) -> int:
        from press.genpass import generate_password

        password = generate_password(length=a.length, symbols=a.symbols)
        sys.stdout.write(password)
        sys.stdout.flush()
        # On a TTY, auto-write to clipboard so the password is immediately pasteable.
        # --no-clip (-N) suppresses this to avoid overwriting an existing clipboard value.
        wrote_clipboard = False
        if (a.clip_out or sys.stdout.isatty()) and not a.no_clip:
            # sensitive=True keeps the password out of the Win+V clipboard
            # history and Cloud Clipboard sync (KeePassXC-style exclusion).
            wrote_clipboard = write_clipboard_or_warn(
                password, cmd="genpass", quiet=a.quiet, sensitive=True
            )
        if a.clear_after:
            if wrote_clipboard:
                _genpass_clear_after(a.clear_after, quiet=a.quiet)
            elif not a.quiet:
                print(
                    "press genpass: warning: --clear-after ignored (no clipboard write)",
                    file=sys.stderr,
                )
        return 0

    p.set_defaults(func=_gp)


def _register_uuid_command(sub: _SubParsers) -> None:
    p = sub.add_parser("uuid", help="Generate random UUIDs (version 4)")
    p.add_argument(
        "-n",
        "--count",
        type=bounded_int(1, "count"),
        default=1,
        metavar="N",
        help="Number of UUIDs to generate, one per line (default: 1)",
    )
    p.add_argument("-U", "--upper", action="store_true", help="Uppercase output")
    p.add_argument(
        "-C",
        "--clip-out",
        action="store_true",
        help="Write output to clipboard (also prints to stdout)",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress all stderr output")

    def _uuid(a: argparse.Namespace) -> int:
        import uuid

        values = "\n".join(str(uuid.uuid4()) for _ in range(a.count))
        if a.upper:
            values = values.upper()
        sys.stdout.write(values + "\n")
        sys.stdout.flush()
        if a.clip_out:
            # Mirrors genpass: stdout already delivered the value, so a
            # clipboard failure is a warning, not a command failure.
            write_clipboard_or_warn(values, cmd="uuid", quiet=a.quiet)
        return 0

    p.set_defaults(func=_uuid)


def _register_clipboard_util_commands(sub: _SubParsers) -> None:
    p = sub.add_parser("clear", aliases=["cl"], help="Clear the clipboard")
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress all stderr output")
    p.add_argument(
        "--hold",
        dest="discard_hold",
        action="store_true",
        help="Also discard the saved 'press hold' file without restoring it",
    )

    def _cl(a: argparse.Namespace) -> int:
        from press._cli_helpers import _snapshot_clipboard_for_undo
        from press.clipboard import clear_clipboard

        _snapshot_clipboard_for_undo()  # an accidental clear is undoable
        try:
            clear_clipboard()
        except Exception as exc:
            if not getattr(a, "quiet", False):
                print(f"press clear: error: {exc}", file=sys.stderr)
            return 1
        if a.discard_hold:
            from press.transforms.hold import hold_path

            hold_path().unlink(missing_ok=True)
        return 0

    p.set_defaults(func=_cl)

    p = sub.add_parser(
        "undo",
        help="Restore the clipboard text the last press command overwrote",
        description=(
            "Swap the clipboard with the snapshot taken before the last "
            "clipboard-writing press command (-C transform or clear). "
            "Running undo again swaps back (redo)."
        ),
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress all stderr output")

    def _undo(a: argparse.Namespace) -> int:
        from press.clipboard import get_clipboard_text, set_clipboard_text
        from press.transforms.undo import swap_undo

        try:
            swap_undo(get_clipboard_text, set_clipboard_text)
        except FileNotFoundError:
            if not a.quiet:
                print("press undo: nothing to undo", file=sys.stderr)
            return 1
        except (OSError, RuntimeError) as exc:
            if not a.quiet:
                print(f"press undo: error: {exc}", file=sys.stderr)
            return 1
        return 0

    p.set_defaults(func=_undo)

    p = sub.add_parser(
        "hold",
        help="Save clipboard text; call again to restore it",
        description=(
            "File-based clipboard hold toggle.\n\n"
            "First call: saves the current clipboard text to "
            "%APPDATA%\\press\\hold.txt and prints 'press hold: held'.\n"
            "Second call: restores the saved text to the clipboard and prints "
            "'press hold: released'.\n\n"
            "For real-time protection that survives any application overwriting\n"
            "the clipboard, use the daemon hotkey instead:\n\n"
            "  press daemon start          # start the daemon\n"
            "  Ctrl+Shift+0, then h        # engage ClipboardGuard\n\n"
            "The daemon hold uses a dual-layer guard:\n"
            "  Layer 1 — WM_CLIPBOARDUPDATE monitor restores on any clipboard\n"
            "            change (< 1 ms reaction time).\n"
            "  Layer 2 — WH_KEYBOARD_LL hook intercepts Ctrl+V / Shift+Insert\n"
            "            before the OS dispatches the keystroke (0 ms gap).\n"
            "The tray icon turns red while protection is active."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress all stderr output")

    def _hold(a: argparse.Namespace) -> int:
        from press.clipboard import get_clipboard_text, set_clipboard_text
        from press.transforms.hold import hold_path, toggle_hold_file

        try:
            held = toggle_hold_file(hold_path(), get_clipboard_text, set_clipboard_text)
            if not a.quiet:
                status = "held" if held else "released"
                print(f"press hold: {status}", file=sys.stderr)
        except Exception as exc:
            if not a.quiet:
                print(f"press hold: error: {exc}", file=sys.stderr)
            return 1
        return 0

    p.set_defaults(func=_hold)


# ---------------------------------------------------------------------------
# Argument parser construction
# ---------------------------------------------------------------------------


def make_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    from press._cli_chain import _register_chain_commands
    from press._cli_config import _register_config_commands
    from press._cli_daemon import _register_daemon_commands
    from press._cli_dict import _register_dict_commands
    from press.commands import PARAMETRIC_COMMANDS, SIMPLE_COMMANDS

    parser = argparse.ArgumentParser(
        prog="press",
        description="Clipboard text transformation tool",
    )
    parser.add_argument(
        "--version",
        action=_LazyVersionAction,
        nargs=0,
        help="show program's version number and exit",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Transform commands: parsers and handlers generated from the registry
    all_commands: tuple[SimpleCommand | ParametricCommand, ...] = (
        *SIMPLE_COMMANDS,
        *PARAMETRIC_COMMANDS,
    )
    for cmd in all_commands:
        _register_transform_command(sub, cmd)

    # Special-purpose commands
    _register_chain_commands(sub)
    _register_genpass_command(sub)
    _register_uuid_command(sub)
    _register_dict_commands(sub)
    _register_clipboard_util_commands(sub)
    _register_config_commands(sub)
    _register_daemon_commands(sub)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and dispatch to the appropriate handler."""
    # Ensure UTF-8 I/O; disable newline translation on output (preserves CR/CRLF transforms)
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    # Set locale once at startup so sort_lines / locale.strxfrm use the user's environment locale.
    # Falls back silently to codepoint order if the user's locale is unavailable (e.g. broken
    # Windows "Region for non-Unicode programs" setting).
    with contextlib.suppress(locale.Error):
        locale.setlocale(locale.LC_COLLATE, "")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = make_parser()
    # argcomplete is only needed when the shell-completion hook invokes us,
    # which it signals via _ARGCOMPLETE; skip the import on normal startup.
    if "_ARGCOMPLETE" in os.environ:
        import argcomplete

        argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
