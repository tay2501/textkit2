"""Command-line entry point for press."""

import argparse
import contextlib
import locale
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
    """Read input: clipboard (TTY default), positional arg, stdin pipe, or '-' sentinel."""
    if getattr(args, "clip_in", False):
        from press.clipboard import get_clipboard_text

        return get_clipboard_text()
    inp = getattr(args, "input", None)
    if inp is not None and inp != "-":
        return str(inp)
    # "-" forces stdin; non-TTY (pipe/redirect) also uses stdin
    if inp == "-" or not sys.stdin.isatty():
        return sys.stdin.read()
    # TTY with no input → clipboard is the default
    from press.clipboard import get_clipboard_text

    return get_clipboard_text()


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
    cmd = getattr(args, "command", "press")
    try:
        text = _read_input(args)
    except Exception as exc:
        if not getattr(args, "quiet", False):
            print(f"press {cmd}: error: failed to read input: {exc}", file=sys.stderr)
        return 1

    try:
        result = fn(text, **kwargs)
    except Exception as exc:
        if getattr(args, "fallback", False):
            _write_output(text, args)
            return 0
        if not getattr(args, "quiet", False):
            print(f"press {cmd}: error: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "verbose", False) and not getattr(args, "quiet", False):
        print(f"before: {text!r}", file=sys.stderr)
        print(f"after:  {result!r}", file=sys.stderr)

    _write_output(result, args)
    return 0


# ---------------------------------------------------------------------------
# Argument parser construction
# ---------------------------------------------------------------------------


def _add_io_args(parser: argparse.ArgumentParser, *, positional: bool = True) -> None:
    """Attach common I/O options to a subcommand parser.

    Pass ``positional=False`` for commands that do not accept inline text input
    (e.g. ``dict``, which always reads from clipboard or a pipeline).
    """
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
    if positional:
        parser.add_argument(
            "input",
            nargs="?",
            default=None,
            help="Input text; omit to read clipboard (TTY) or stdin (pipe); '-' forces stdin",
        )


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
    _add_io_args(dict_p, positional=False)

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


def _register_config_commands(sub: _SubParsers) -> None:
    """Register the ``config`` subcommand family."""
    config_p = sub.add_parser("config", help="Manage press configuration")
    config_sub = config_p.add_subparsers(dest="config_action", metavar="ACTION")
    config_p.set_defaults(func=_handle_config)

    _file_arg: dict[str, object] = {
        "metavar": "PATH",
        "default": None,
        "help": "Config file (default: platform path)",
    }

    val_p = config_sub.add_parser("validate", help="Parse config.toml and report errors")
    val_p.add_argument("--file", **_file_arg)  # type: ignore[arg-type]

    rst_p = config_sub.add_parser(
        "reset",
        help="Reset config to defaults and create a .toml.bak backup",
    )
    rst_p.add_argument(
        "--key",
        choices=["hotkeys", "sql_in", "dictionary", "ui", "hold"],
        default=None,
        metavar="SECTION",
        help="Section to reset; omit to reset the entire file",
    )
    rst_p.add_argument("--file", **_file_arg)  # type: ignore[arg-type]


def _handle_config(args: argparse.Namespace) -> int:
    from pathlib import Path

    from press.config import config_reset, config_validate, default_config_path

    raw_file: str | None = getattr(args, "file", None)
    cfg_path = Path(raw_file) if raw_file else default_config_path()

    action: str | None = getattr(args, "config_action", None)
    if action is None:
        import subprocess

        subprocess.run([sys.argv[0], "config", "--help"], check=False)
        return 0

    match action:
        case "validate":
            ok, msg = config_validate(cfg_path)
            print(f"press config validate: {msg}", file=sys.stdout if ok else sys.stderr)
            return 0 if ok else 1
        case "reset":
            key: str | None = getattr(args, "key", None)
            try:
                backed_up = config_reset(cfg_path, key=key)
                if backed_up:
                    print(
                        f"press config reset: backup saved to {cfg_path.with_suffix('.toml.bak')}"
                    )
                section = f" [{key}]" if key else ""
                print(f"press config reset: config{section} reset to defaults → {cfg_path}")
                return 0
            except Exception as exc:
                print(f"press config reset: error: {exc}", file=sys.stderr)
                return 1
        case _:
            return 1


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


def _handle_daemon(args: argparse.Namespace) -> int:
    action = getattr(args, "daemon_action", None)
    if action is None:
        # `press daemon` with no subcommand — print daemon help
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
