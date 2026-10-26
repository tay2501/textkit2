"""CLI registration for the ``dict`` command group."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from press._cli_helpers import _add_io_args, _run_transform

if TYPE_CHECKING:
    from pathlib import Path

    from press._cli_helpers import _SubParsers

_FILE_HELP = "TSV dictionary file (default: [dictionary] files in config.toml)"


def _register_dict_commands(sub: _SubParsers) -> None:
    """Register the ``dict`` command group and its management subcommands."""
    dict_p = sub.add_parser("dict", help="Dictionary-based text replacement")
    dict_p.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        help="Apply reverse lookup (value→key instead of key→value)",
    )
    dict_p.add_argument("--file", metavar="PATH", default=None, help=_FILE_HELP)
    _add_io_args(dict_p, positional=False)

    dict_sub = dict_p.add_subparsers(dest="dict_action", metavar="ACTION")

    def action_parser(name: str, help_text: str, *, aliases: list[str]) -> argparse.ArgumentParser:
        p = dict_sub.add_parser(name, aliases=aliases, help=help_text)
        # argparse records the name as typed, so pin the canonical one for the
        # handler's match; an alias would otherwise fall through to "transform".
        p.set_defaults(func=_dict_handler, dict_action=name)
        # SUPPRESS: a subparser's own default would overwrite a --file given
        # before the action (press dict --file X list).
        p.add_argument("--file", metavar="PATH", default=argparse.SUPPRESS, help=_FILE_HELP)
        return p

    action_parser("list", "List all dictionary entries", aliases=["ls"])
    add_p = action_parser("add", "Add an entry to the dictionary", aliases=[])
    add_p.add_argument("key", help="Entry key")
    add_p.add_argument("value", help="Entry value")
    rm_p = action_parser("remove", "Remove an entry from the dictionary", aliases=["rm"])
    rm_p.add_argument("key", help="Key to remove")

    dict_p.set_defaults(func=_dict_handler)


def _dict_path(raw_file: str | None) -> Path:
    """Return ``--file``, else the file the daemon reads too.

    Raises:
        ValueError: When config.toml cannot be read.
    """
    from pathlib import Path

    if raw_file:
        return Path(raw_file)
    from press.config import load_config
    from press.dictionary import configured_dict_path

    return configured_dict_path(load_config().dictionary)


def _dict_handler(a: argparse.Namespace) -> int:
    from press.dictionary import add_entry, list_entries, remove_entry
    from press.transforms.dictionary import dict_forward, dict_reverse, load_tsv

    action: str | None = getattr(a, "dict_action", None)
    raw_file: str | None = getattr(a, "file", None)
    try:
        dict_path = _dict_path(raw_file)
    except ValueError as exc:
        print(f"press dict: error: {exc}", file=sys.stderr)
        return 1

    def not_found() -> int:
        print(f"press dict: error: dictionary file not found: {dict_path}", file=sys.stderr)
        return 1

    match action:
        case "list":
            try:
                entries = list_entries(dict_path)
            except FileNotFoundError:
                # No dictionary yet is an empty list; a file the user named
                # must exist.
                return not_found() if raw_file else 0
            for key, value in entries:
                sys.stdout.write(f"{key}\t{value}\n")
            return 0

        case "add":
            add_entry(a.key, a.value, dict_path)
            return 0

        case "remove":
            try:
                found = remove_entry(a.key, dict_path)
            except FileNotFoundError:
                found = False
            if not found:
                print(f"press dict remove: error: key not found: {a.key}", file=sys.stderr)
                return 1
            return 0

        case _:
            # No subcommand — run as a transform
            try:
                table = load_tsv(dict_path)
            except FileNotFoundError:
                return not_found()
            fn = dict_reverse if getattr(a, "reverse", False) else dict_forward
            return _run_transform(fn, a, table=table)
