"""Command-line entry point for press."""

import argparse
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from press.commands import SimpleCommand

# Convenience alias for the subparsers action type
type _SubParsers = argparse._SubParsersAction[argparse.ArgumentParser]


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("press")
    except PackageNotFoundError:
        return "unknown"


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _read_input(args: argparse.Namespace) -> str:
    """Read input from stdin, clipboard, or positional argument."""
    if getattr(args, "clip_in", False):
        from press.clipboard import get_clipboard_text

        return get_clipboard_text()
    if getattr(args, "input", None) is not None:
        return str(args.input)
    return sys.stdin.read()


def _write_output(text: str, args: argparse.Namespace) -> None:
    """Write output to stdout and optionally to clipboard."""
    sys.stdout.write(text)
    sys.stdout.flush()
    if getattr(args, "clip_out", False):
        from press.clipboard import set_clipboard_text

        set_clipboard_text(text)


def _run_transform(
    fn: Callable[..., str],
    args: argparse.Namespace,
    **kwargs: Any,
) -> int:
    """Read → transform → write.  Returns an exit code (0 = success, 1 = error)."""
    _cmd = getattr(args, "command", "press")
    try:
        text = _read_input(args)
    except Exception as exc:
        if not getattr(args, "quiet", False):
            print(f"press {_cmd}: error: failed to read input: {exc}", file=sys.stderr)
        return 1

    try:
        result = fn(text, **kwargs)
    except Exception as exc:
        if getattr(args, "fallback", False):
            _write_output(text, args)
            return 0
        if not getattr(args, "quiet", False):
            print(f"press {_cmd}: error: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "verbose", False) and not getattr(args, "quiet", False):
        print(f"before: {text!r}", file=sys.stderr)
        print(f"after:  {result!r}", file=sys.stderr)

    _write_output(result, args)
    return 0


# ---------------------------------------------------------------------------
# Argument parser construction
# ---------------------------------------------------------------------------


def _add_io_args(parser: argparse.ArgumentParser) -> None:
    """Attach common I/O options to a subcommand parser."""
    parser.add_argument("-c", "--clip-in", action="store_true", help="Read input from clipboard")
    parser.add_argument(
        "-C",
        "--clip-out",
        action="store_true",
        help="Write output to clipboard (also prints to stdout)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show before/after on stderr")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress all stderr output")
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="On transform error, output original text and exit 0",
    )
    parser.add_argument("input", nargs="?", default=None, help="Input text (default: stdin)")


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


def _add_dict_io_args(parser: argparse.ArgumentParser) -> None:
    """Attach I/O options for the dict transform subcommand (no positional input)."""
    parser.add_argument("-c", "--clip-in", action="store_true", help="Read input from clipboard")
    parser.add_argument(
        "-C",
        "--clip-out",
        action="store_true",
        help="Write output to clipboard (also prints to stdout)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show before/after on stderr")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress all stderr output")
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="On transform error, output original text and exit 0",
    )


def _register_dict_commands(sub: _SubParsers) -> None:
    """Register the ``dict`` command group and its management subcommands."""
    dict_p = sub.add_parser("dict", help="Dictionary-based text replacement (F-08, F-09)")
    dict_p.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        help="Apply reverse lookup (value→key instead of key→value)",
    )
    dict_p.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="TSV dictionary file (default: platform config path)",
    )
    _add_dict_io_args(dict_p)

    dict_sub = dict_p.add_subparsers(dest="dict_action", metavar="ACTION")

    # --- dict list ---
    list_p = dict_sub.add_parser("list", help="List all dictionary entries")
    list_p.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="TSV dictionary file (default: platform config path)",
    )

    # --- dict add ---
    add_p = dict_sub.add_parser("add", help="Add an entry to the dictionary")
    add_p.add_argument("key", help="Entry key")
    add_p.add_argument("value", help="Entry value")
    add_p.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="TSV dictionary file (default: platform config path)",
    )

    # --- dict remove ---
    rm_p = dict_sub.add_parser("remove", aliases=["rm"], help="Remove an entry from the dictionary")
    rm_p.add_argument("key", help="Key to remove")
    rm_p.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="TSV dictionary file (default: platform config path)",
    )

    def _dict_handler(a: argparse.Namespace) -> int:
        from pathlib import Path

        from press.dictionary import add_entry, default_dict_path, list_entries, remove_entry
        from press.transforms.dictionary import dict_forward, dict_reverse, load_tsv

        # Resolve the --file argument from whichever parser captured it
        raw_file: str | None = getattr(a, "file", None)
        dict_path = Path(raw_file) if raw_file else default_dict_path()

        action: str | None = getattr(a, "dict_action", None)

        match action:
            case "list":
                try:
                    entries = list_entries(dict_path)
                except FileNotFoundError:
                    print(
                        f"press dict: error: dict file not found: {dict_path}",
                        file=sys.stderr,
                    )
                    return 2
                for key, value in entries:
                    sys.stdout.write(f"{key}\t{value}\n")
                return 0

            case "add":
                add_entry(a.key, a.value, dict_path)
                return 0

            case "remove" | "rm":
                try:
                    found = remove_entry(a.key, dict_path)
                except FileNotFoundError:
                    print(
                        f"press dict: error: dict file not found: {dict_path}",
                        file=sys.stderr,
                    )
                    return 2
                if not found:
                    print(
                        f"press dict remove: error: key not found: {a.key}",
                        file=sys.stderr,
                    )
                    return 1
                return 0

            case _:
                # No subcommand — run as a transform
                try:
                    table = load_tsv(dict_path)
                except FileNotFoundError:
                    print(
                        f"press dict: error: dict file not found: {dict_path}",
                        file=sys.stderr,
                    )
                    return 2
                fn = dict_reverse if getattr(a, "reverse", False) else dict_forward
                return _run_transform(fn, a, table=table)

    dict_p.set_defaults(func=_dict_handler)
    list_p.set_defaults(func=_dict_handler)
    add_p.set_defaults(func=_dict_handler)
    rm_p.set_defaults(func=_dict_handler)


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

    p = sub.add_parser("hold", help="Toggle clipboard hold (save/restore)")
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


def _register_daemon_commands(sub: _SubParsers) -> None:
    daemon_p = sub.add_parser("daemon", help="Manage press background daemon")
    daemon_p.add_argument(
        "action",
        choices=["start", "stop", "status", "restart"],
        help="Daemon action",
    )
    daemon_p.set_defaults(func=_handle_daemon)


def make_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
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
    _register_sql_commands(sub)
    _register_encoding_repair_commands(sub)
    _register_json_format_command(sub)

    # Special-purpose commands
    _register_dict_commands(sub)
    _register_clipboard_util_commands(sub)
    _register_daemon_commands(sub)

    return parser


def _handle_daemon(args: argparse.Namespace) -> int:
    match args.action:
        case "start":
            from press.daemon import run_daemon

            run_daemon()
            return 0
        case "stop":
            from press.daemon import stop_daemon

            return stop_daemon()
        case "status":
            from press.daemon import daemon_status

            return daemon_status()
        case "restart":
            from press.daemon import run_daemon, stop_daemon

            stop_daemon()
            run_daemon()
            return 0
        case _:
            return 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and dispatch to the appropriate handler."""
    # Ensure UTF-8 I/O; disable newline translation on output (preserves CR/CRLF transforms)
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
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
