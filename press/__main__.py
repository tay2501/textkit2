"""Command-line entry point for press."""

import argparse
import sys
from collections.abc import Callable
from typing import Any

# Convenience alias for the subparsers action type
type _SubParsers = argparse._SubParsersAction[argparse.ArgumentParser]


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


def _register_width_commands(sub: _SubParsers) -> None:
    p = sub.add_parser(
        "halfwidth", aliases=["hw"], help="Convert full-width characters to half-width"
    )
    _add_io_args(p)

    def _hw(a: argparse.Namespace) -> int:
        from press.transforms.width import to_halfwidth

        return _run_transform(to_halfwidth, a)

    p.set_defaults(func=_hw)

    p = sub.add_parser(
        "fullwidth", aliases=["fw"], help="Convert half-width characters to full-width"
    )
    _add_io_args(p)

    def _fw(a: argparse.Namespace) -> int:
        from press.transforms.width import to_fullwidth

        return _run_transform(to_fullwidth, a)

    p.set_defaults(func=_fw)


def _register_whitespace_commands(sub: _SubParsers) -> None:
    p = sub.add_parser("normalize", aliases=["norm"], help="Normalize whitespace and blank lines")
    _add_io_args(p)

    def _norm(a: argparse.Namespace) -> int:
        from press.transforms.whitespace import normalize_whitespace

        return _run_transform(normalize_whitespace, a)

    p.set_defaults(func=_norm)


def _register_lineending_commands(sub: _SubParsers) -> None:
    p = sub.add_parser("crlf", help=r"Convert line endings to CRLF (\r\n)")
    _add_io_args(p)

    def _crlf(a: argparse.Namespace) -> int:
        from press.transforms.lineending import to_crlf

        return _run_transform(to_crlf, a)

    p.set_defaults(func=_crlf)

    p = sub.add_parser("lf", help=r"Convert line endings to LF (\n)")
    _add_io_args(p)

    def _lf(a: argparse.Namespace) -> int:
        from press.transforms.lineending import to_lf

        return _run_transform(to_lf, a)

    p.set_defaults(func=_lf)

    p = sub.add_parser("cr", help=r"Convert line endings to CR (\r)")
    _add_io_args(p)

    def _cr(a: argparse.Namespace) -> int:
        from press.transforms.lineending import to_cr

        return _run_transform(to_cr, a)

    p.set_defaults(func=_cr)


def _register_separator_commands(sub: _SubParsers) -> None:
    p = sub.add_parser("underscore", aliases=["us"], help="Convert hyphens to underscores")
    _add_io_args(p)

    def _us(a: argparse.Namespace) -> int:
        from press.transforms.separator import hyphen_to_underscore

        return _run_transform(hyphen_to_underscore, a)

    p.set_defaults(func=_us)

    p = sub.add_parser("hyphen", aliases=["hy"], help="Convert underscores to hyphens")
    _add_io_args(p)

    def _hy(a: argparse.Namespace) -> int:
        from press.transforms.separator import underscore_to_hyphen

        return _run_transform(underscore_to_hyphen, a)

    p.set_defaults(func=_hy)


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


def _register_escape_commands(sub: _SubParsers) -> None:
    p = sub.add_parser(
        "unicode-decode", aliases=["ud"], help=r"Decode \uXXXX escape sequences to text"
    )
    _add_io_args(p)

    def _ud(a: argparse.Namespace) -> int:
        from press.transforms.escape import decode_unicode_escape

        return _run_transform(decode_unicode_escape, a)

    p.set_defaults(func=_ud)

    p = sub.add_parser(
        "unicode-encode", aliases=["ue"], help=r"Encode text to \uXXXX escape sequences"
    )
    _add_io_args(p)

    def _ue(a: argparse.Namespace) -> int:
        from press.transforms.escape import encode_unicode_escape

        return _run_transform(encode_unicode_escape, a)

    p.set_defaults(func=_ue)

    p = sub.add_parser("html-decode", aliases=["hd"], help="Decode HTML entities (e.g. &amp; → &)")
    _add_io_args(p)

    def _hd(a: argparse.Namespace) -> int:
        from press.transforms.escape import decode_html_entities

        return _run_transform(decode_html_entities, a)

    p.set_defaults(func=_hd)


def _register_case_commands(sub: _SubParsers) -> None:
    p = sub.add_parser("snake", aliases=["sn"], help="Convert to snake_case")
    _add_io_args(p)

    def _sn(a: argparse.Namespace) -> int:
        from press.transforms.case import to_snake_case

        return _run_transform(to_snake_case, a)

    p.set_defaults(func=_sn)

    p = sub.add_parser("camel", aliases=["cm"], help="Convert to camelCase")
    _add_io_args(p)

    def _cm(a: argparse.Namespace) -> int:
        from press.transforms.case import to_camel_case

        return _run_transform(to_camel_case, a)

    p.set_defaults(func=_cm)

    p = sub.add_parser("pascal", aliases=["pc"], help="Convert to PascalCase")
    _add_io_args(p)

    def _pc(a: argparse.Namespace) -> int:
        from press.transforms.case import to_pascal_case

        return _run_transform(to_pascal_case, a)

    p.set_defaults(func=_pc)

    p = sub.add_parser("kebab", aliases=["kb"], help="Convert to kebab-case")
    _add_io_args(p)

    def _kb(a: argparse.Namespace) -> int:
        from press.transforms.case import to_kebab_case

        return _run_transform(to_kebab_case, a)

    p.set_defaults(func=_kb)


def _register_encode_commands(sub: _SubParsers) -> None:
    p = sub.add_parser("base64-encode", aliases=["be"], help="Encode text to Base64")
    _add_io_args(p)

    def _be(a: argparse.Namespace) -> int:
        from press.transforms.encode import base64_encode

        return _run_transform(base64_encode, a)

    p.set_defaults(func=_be)

    p = sub.add_parser("base64-decode", aliases=["bd"], help="Decode Base64 to text")
    _add_io_args(p)

    def _bd(a: argparse.Namespace) -> int:
        from press.transforms.encode import base64_decode

        return _run_transform(base64_decode, a)

    p.set_defaults(func=_bd)

    p = sub.add_parser("url-encode", aliases=["ue2"], help="Percent-encode URL text")
    _add_io_args(p)

    def _ue2(a: argparse.Namespace) -> int:
        from press.transforms.encode import url_encode

        return _run_transform(url_encode, a)

    p.set_defaults(func=_ue2)

    p = sub.add_parser("url-decode", aliases=["ud2"], help="Decode percent-encoded URL text")
    _add_io_args(p)

    def _ud2(a: argparse.Namespace) -> int:
        from press.transforms.encode import url_decode

        return _run_transform(url_decode, a)

    p.set_defaults(func=_ud2)


def _register_json_commands(sub: _SubParsers) -> None:
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

    p = sub.add_parser("json-compress", aliases=["jc"], help="Compress JSON to single line")
    _add_io_args(p)

    def _jc(a: argparse.Namespace) -> int:
        from press.transforms.json_fmt import json_compress

        return _run_transform(json_compress, a)

    p.set_defaults(func=_jc)


def _register_daemon_commands(sub: _SubParsers) -> None:
    daemon_p = sub.add_parser("daemon", help="Manage press daemon (not yet implemented)")
    daemon_p.add_argument(
        "action",
        choices=["start", "stop", "status", "restart"],
        help="Daemon action",
    )
    daemon_p.set_defaults(func=_handle_daemon)


def make_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="press",
        description="Clipboard text transformation tool",
    )
    parser.add_argument("--version", action="version", version=f"press {_version()}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    _register_width_commands(sub)
    _register_whitespace_commands(sub)
    _register_lineending_commands(sub)
    _register_separator_commands(sub)
    _register_sql_commands(sub)
    _register_escape_commands(sub)
    _register_case_commands(sub)
    _register_encode_commands(sub)
    _register_json_commands(sub)
    _register_daemon_commands(sub)

    return parser


def _handle_daemon(args: argparse.Namespace) -> int:
    print(
        f"press daemon: error: {args.action} is not yet implemented",
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
    import argcomplete

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
