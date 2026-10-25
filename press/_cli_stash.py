"""CLI registration for the ``stash`` command group.

``press stash push|pop|drop|list`` keeps one saved clipboard text in
``%APPDATA%\\press\\stash.txt``, with the verbs of ``git stash``.  Unlike
``git stash``, a bare ``press stash`` prints help instead of pushing: the slot
holds one entry, and an implicit push would fail half the time.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable
    from pathlib import Path

    from press._cli_helpers import _SubParsers


def _register_stash_commands(sub: _SubParsers) -> None:
    """Register the ``stash`` subcommand family."""
    from press.commands import special_aliases

    stash_p = sub.add_parser(
        "stash",
        aliases=special_aliases("stash"),
        help="Save the clipboard text and restore it later (one slot)",
        description=(
            "Save the clipboard text and restore it later.\n\n"
            "  press stash push   save the clipboard text (fails if one is saved)\n"
            "  press stash pop    restore it to the clipboard and delete it\n"
            "  press stash drop   delete it without restoring\n"
            "  press stash list   show whether one is saved (length only)\n\n"
            "The text is stored DPAPI-encrypted in %APPDATA%\\press\\stash.txt, and a\n"
            "password copied by genpass is restored with its clipboard-history\n"
            "exclusion. A stash does not protect the clipboard; to block overwrites\n"
            "until you release it, use the daemon's ClipboardGuard\n"
            "(Ctrl+Alt+K, then h,o)."
        ),
    )
    stash_sub = stash_p.add_subparsers(dest="stash_action", metavar="ACTION")
    # print_help: shown when no ACTION is given (see _handle_stash).
    stash_p.set_defaults(func=_handle_stash, print_help=stash_p.print_help)

    for action, help_text in (
        ("push", "Save the clipboard text"),
        ("pop", "Restore the saved text to the clipboard and delete it"),
        ("drop", "Delete the saved text without restoring it"),
        ("list", "Show whether a text is saved and its length"),
    ):
        p = stash_sub.add_parser(action, help=help_text)
        p.add_argument("-q", "--quiet", action="store_true", help="Suppress all stderr output")


def _handle_stash(args: argparse.Namespace) -> int:
    action: str | None = getattr(args, "stash_action", None)
    if action is None:
        args.print_help()
        return 0

    from press._cli_helpers import report_error
    from press.transforms.stash import stash_path

    quiet: bool = args.quiet
    path = stash_path()

    def say(message: str) -> None:
        if not quiet:
            print(f"press stash: {message}", file=sys.stderr)

    try:
        match action:
            case "push":
                return _push(path, say)
            case "pop":
                return _pop(path, say)
            case "drop":
                from press.transforms.stash import drop

                drop(path)
                say("dropped")
                return 0
            case "list":
                from press.transforms.stash import stashed

                text, sensitive = stashed(path)
                mark = ", sensitive" if sensitive else ""
                print(f"press stash: {len(text)} characters{mark}")
                return 0
            case _:
                return 1
    except FileNotFoundError:
        if action == "list":
            return 0  # an empty list, like `git stash list`
        say("error: no stash to restore or drop")
        return 1
    # Clipboard (OSError/RuntimeError), file (OSError) and DPAPI or a corrupt
    # file (RuntimeError) failures.
    except (OSError, RuntimeError) as exc:
        return report_error("stash", exc, quiet=quiet)


def _push(path: Path, say: Callable[[str], None]) -> int:
    from press.clipboard import clipboard_has_sensitive_marks, get_clipboard_text
    from press.transforms.stash import push

    text = get_clipboard_text()
    try:
        sensitive = clipboard_has_sensitive_marks()
    except (OSError, RuntimeError):
        sensitive = True  # unreadable marks: restore as a secret, never leak one
    try:
        push(path, text, sensitive=sensitive)
    except FileExistsError:
        say("error: a text is already stashed; run 'press stash pop' or 'drop' first")
        return 1
    say(f"saved {len(text)} characters")
    return 0


def _pop(path: Path, say: Callable[[str], None]) -> int:
    from press._cli_helpers import _snapshot_clipboard_for_undo
    from press.clipboard import set_clipboard_text
    from press.transforms.stash import pop

    def restore(text: str, sensitive: bool) -> None:
        _snapshot_clipboard_for_undo()  # the restore overwrites the clipboard
        set_clipboard_text(text, sensitive=sensitive)

    pop(path, restore)
    say("restored")
    return 0
