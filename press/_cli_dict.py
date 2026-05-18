"""CLI registration for the ``dict`` command group."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from press._cli_helpers import _add_io_args, _run_transform

if TYPE_CHECKING:
    import argparse

    from press._cli_helpers import _SubParsers


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
