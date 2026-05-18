"""Command-line entry point for press."""

import argparse
import contextlib
import locale
import sys
from typing import TYPE_CHECKING

from press._cli_helpers import _add_io_args, _run_transform, _SubParsers

if TYPE_CHECKING:
    from press.commands import SimpleCommand


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("press")
    except PackageNotFoundError:
        return "unknown"


# ---------------------------------------------------------------------------
# Simple command registration
# ---------------------------------------------------------------------------


def _register_simple_command(sub: _SubParsers, cmd: "SimpleCommand") -> None:
    """Register one simple transform command from the central registry.

    "Simple" means: no extra CLI arguments beyond the standard I/O flags.
    The transform function signature is ``fn(text: str) -> str``.
    """
    import importlib

    p = sub.add_parser(cmd.name, aliases=list(cmd.aliases), help=cmd.help)
    _add_io_args(p)

    # Bind cmd as a default argument to avoid the loop late-binding pitfall.
    def _handler(a: argparse.Namespace, _cmd: "SimpleCommand" = cmd) -> int:
        fn = getattr(importlib.import_module(_cmd.module), _cmd.fn)
        return _run_transform(fn, a)

    p.set_defaults(func=_handler)


# ---------------------------------------------------------------------------
# Parametric command registration
# ---------------------------------------------------------------------------


def _register_trim_command(sub: _SubParsers) -> None:
    p = sub.add_parser("trim", aliases=["tm"], help="Strip trailing whitespace from each line")
    _add_io_args(p)
    p.add_argument(
        "--both",
        "-b",
        action="store_true",
        help="Strip leading and trailing whitespace (str.strip())",
    )

    def _trim(a: argparse.Namespace) -> int:
        from press.transforms.lines import trim_lines

        return _run_transform(trim_lines, a, both=a.both)

    p.set_defaults(func=_trim)


def _register_dedupe_command(sub: _SubParsers) -> None:
    p = sub.add_parser("dedupe", aliases=["dq"], help="Remove duplicate lines")
    _add_io_args(p)
    p.add_argument("--ignore-case", "-i", action="store_true", help="Case-insensitive comparison")
    p.add_argument(
        "--adjacent",
        "-a",
        action="store_true",
        help="Remove only adjacent duplicates (like GNU uniq)",
    )

    def _dd(a: argparse.Namespace) -> int:
        from press.transforms.lines import dedupe_lines

        return _run_transform(dedupe_lines, a, ignore_case=a.ignore_case, adjacent=a.adjacent)

    p.set_defaults(func=_dd)


def _register_sort_command(sub: _SubParsers) -> None:
    p = sub.add_parser("sort", aliases=["st"], help="Sort lines")
    _add_io_args(p)
    p.add_argument("--reverse", "-r", action="store_true", help="Reverse sort order")
    p.add_argument(
        "--numeric",
        "-n",
        action="store_true",
        help="Numeric sort; non-numeric lines go last",
    )
    p.add_argument("--ignore-case", "-i", action="store_true", help="Case-insensitive sort")

    def _st(a: argparse.Namespace) -> int:
        from press.transforms.lines import sort_lines

        return _run_transform(
            sort_lines, a, reverse=a.reverse, numeric=a.numeric, ignore_case=a.ignore_case
        )

    p.set_defaults(func=_st)


def _register_sql_commands(sub: _SubParsers) -> None:
    p = sub.add_parser(
        "sql-in", aliases=["sq"], help="Convert newline-separated values to SQL IN clause"
    )
    _add_io_args(p)
    p.add_argument("--quote-char", default="'", metavar="CHAR", help="Quote character (default: ')")
    p.add_argument("--wrap", action="store_true", help="Wrap result in parentheses")

    def _sq(a: argparse.Namespace) -> int:
        from press.transforms.sql import to_sql_in

        return _run_transform(to_sql_in, a, quote_char=a.quote_char, wrap=a.wrap)

    p.set_defaults(func=_sq)


def _register_encoding_repair_commands(sub: _SubParsers) -> None:
    p = sub.add_parser(
        "fix-encoding",
        aliases=["fe"],
        help="Repair mojibake text by detecting and re-decoding the original encoding (F-15)",
    )
    _add_io_args(p)
    p.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        metavar="N",
        help="Minimum confidence to accept detected encoding (default: 0.7)",
    )

    def _fe(a: argparse.Namespace) -> int:
        from press.transforms.encoding_repair import fix_encoding

        return _run_transform(fix_encoding, a, confidence_threshold=a.threshold)

    p.set_defaults(func=_fe)


def _register_json_format_command(sub: _SubParsers) -> None:
    p = sub.add_parser("json-format", aliases=["jf"], help="Pretty-print JSON")
    _add_io_args(p)
    p.add_argument(
        "--indent",
        type=int,
        default=2,
        metavar="N",
        help="Indentation spaces (default: 2)",
    )

    def _jf(a: argparse.Namespace) -> int:
        from press.transforms.json_fmt import json_format

        return _run_transform(json_format, a, indent=a.indent)

    p.set_defaults(func=_jf)


def _register_clipboard_util_commands(sub: _SubParsers) -> None:
    p = sub.add_parser("clear", aliases=["cl"], help="Clear the clipboard")
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress all stderr output")

    def _cl(a: argparse.Namespace) -> int:
        from press.clipboard import clear_clipboard

        try:
            clear_clipboard()
        except Exception as exc:
            if not getattr(a, "quiet", False):
                print(f"press clear: error: {exc}", file=sys.stderr)
            return 1
        return 0

    p.set_defaults(func=_cl)

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
            "  Ctrl+Shift+F10 → h         # engage ClipboardGuard\n\n"
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
    from press._cli_config import _register_config_commands
    from press._cli_daemon import _register_daemon_commands
    from press._cli_dict import _register_dict_commands
    from press.commands import SIMPLE_COMMANDS

    parser = argparse.ArgumentParser(
        prog="press",
        description="Clipboard text transformation tool",
    )
    parser.add_argument("--version", action="version", version=f"press {_version()}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Simple commands: no extra arguments beyond the standard I/O flags
    for cmd in SIMPLE_COMMANDS:
        _register_simple_command(sub, cmd)

    # Parametric commands: require extra CLI arguments
    _register_trim_command(sub)
    _register_dedupe_command(sub)
    _register_sort_command(sub)
    _register_sql_commands(sub)
    _register_encoding_repair_commands(sub)
    _register_json_format_command(sub)

    # Special-purpose commands
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
    import argcomplete

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
