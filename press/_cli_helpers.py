"""Shared CLI helpers: I/O, transform runner, argparse decorators."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

type _SubParsers = argparse._SubParsersAction[argparse.ArgumentParser]


def bounded_int(minimum: int, label: str) -> Callable[[str], int]:
    """Build an argparse ``type`` that parses an int and enforces a lower bound.

    Shared by the generator commands (``genpass`` length/clear-after, ``uuid``
    count) so the ``>= N`` validation and its message live in one place.
    """

    def _parse(value: str) -> int:
        n = int(value)
        if n < minimum:
            raise argparse.ArgumentTypeError(f"{label} must be >= {minimum}, got {n}")
        return n

    return _parse


def write_clipboard_or_warn(text: str, *, cmd: str, quiet: bool, sensitive: bool = False) -> bool:
    """Write *text* to the clipboard, printing a warning (not failing) on error.

    Returns whether the write succeeded.  The generator commands already
    delivered their value on stdout, so a clipboard failure is advisory.
    """
    try:
        from press.clipboard import set_clipboard_text

        set_clipboard_text(text, sensitive=sensitive)
    except Exception as exc:
        if not quiet:
            print(f"press {cmd}: warning: clipboard write failed: {exc}", file=sys.stderr)
        return False
    return True


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
    quiet = getattr(args, "quiet", False)
    try:
        text = _read_input(args)
    except Exception as exc:
        if not quiet:
            print(f"press {cmd}: error: failed to read input: {exc}", file=sys.stderr)
        return 1

    try:
        result = fn(text, **kwargs)
    except Exception as exc:
        if getattr(args, "fallback", False):
            _write_output(text, args)
            return 0
        if not quiet:
            print(f"press {cmd}: error: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "verbose", False) and not quiet:
        print(f"before: {text!r}", file=sys.stderr)
        print(f"after:  {result!r}", file=sys.stderr)

    _write_output(result, args)
    return 0


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
