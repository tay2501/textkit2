"""Command-line entry point for press."""

import argparse
import sys
from collections.abc import Callable
from typing import Any

from press.transforms.escape import (
    decode_html_entities,
    decode_unicode_escape,
    encode_unicode_escape,
)
from press.transforms.lineending import to_cr, to_crlf, to_lf
from press.transforms.separator import hyphen_to_underscore, underscore_to_hyphen
from press.transforms.sql import to_sql_in
from press.transforms.whitespace import normalize_whitespace
from press.transforms.width import to_fullwidth, to_halfwidth


def _version() -> str:
    try:
        from importlib.metadata import version

        return version("press")
    except Exception:
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
    try:
        text = _read_input(args)
    except Exception as exc:
        if not getattr(args, "quiet", False):
            print(f"press: failed to read input: {exc}", file=sys.stderr)
        return 1

    try:
        result = fn(text, **kwargs)
    except Exception as exc:
        if getattr(args, "fallback", False):
            _write_output(text, args)
            return 0
        if not getattr(args, "quiet", False):
            print(f"press: {exc}", file=sys.stderr)
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


def make_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="press",
        description="Clipboard text transformation tool",
    )
    parser.add_argument("--version", action="version", version=f"press {_version()}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # --- width ---
    p = sub.add_parser(
        "halfwidth", aliases=["hw"], help="Convert full-width characters to half-width"
    )
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(to_halfwidth, a))

    p = sub.add_parser(
        "fullwidth", aliases=["fw"], help="Convert half-width characters to full-width"
    )
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(to_fullwidth, a))

    # --- whitespace ---
    p = sub.add_parser("normalize", aliases=["norm"], help="Normalize whitespace and blank lines")
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(normalize_whitespace, a))

    # --- line endings ---
    p = sub.add_parser("crlf", help="Convert line endings to CRLF (\\r\\n)")
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(to_crlf, a))

    p = sub.add_parser("lf", help="Convert line endings to LF (\\n)")
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(to_lf, a))

    p = sub.add_parser("cr", help="Convert line endings to CR (\\r)")
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(to_cr, a))

    # --- separators ---
    p = sub.add_parser("underscore", aliases=["us"], help="Convert hyphens to underscores")
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(hyphen_to_underscore, a))

    p = sub.add_parser("hyphen", aliases=["hy"], help="Convert underscores to hyphens")
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(underscore_to_hyphen, a))

    # --- SQL ---
    p = sub.add_parser(
        "sql-in", aliases=["sq"], help="Convert newline-separated values to SQL IN clause"
    )
    _add_io_args(p)
    p.add_argument("--quote-char", default="'", metavar="CHAR", help="Quote character (default: ')")
    p.add_argument("--wrap", action="store_true", help="Wrap result in parentheses")
    p.set_defaults(
        func=lambda a: _run_transform(to_sql_in, a, quote_char=a.quote_char, wrap=a.wrap)
    )

    # --- unicode escape ---
    p = sub.add_parser(
        "unicode-decode", aliases=["ud"], help=r"Decode \uXXXX escape sequences to text"
    )
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(decode_unicode_escape, a))

    p = sub.add_parser(
        "unicode-encode", aliases=["ue"], help=r"Encode text to \uXXXX escape sequences"
    )
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(encode_unicode_escape, a))

    # --- HTML ---
    p = sub.add_parser("html-decode", aliases=["hd"], help="Decode HTML entities (e.g. &amp; → &)")
    _add_io_args(p)
    p.set_defaults(func=lambda a: _run_transform(decode_html_entities, a))

    # --- daemon (Phase 2 stub) ---
    daemon_p = sub.add_parser("daemon", help="Manage press daemon (not yet implemented)")
    daemon_p.add_argument(
        "action",
        choices=["start", "stop", "status", "restart"],
        help="Daemon action",
    )
    daemon_p.set_defaults(func=_handle_daemon)

    return parser


def _handle_daemon(args: argparse.Namespace) -> int:
    print(
        f"press: daemon {args.action} is not yet implemented",
        file=sys.stderr,
    )
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
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
