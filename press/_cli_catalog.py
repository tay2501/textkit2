"""Grouped command listing shown when ``press`` is given an unknown command.

Imported only on that error path, so ``difflib``/``shutil`` stay off the
normal CLI startup.
"""

from __future__ import annotations

import difflib
import shutil
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    import argparse

    from press.__main__ import CommandCatalog

_INDENT = "    "


def format_catalog(catalog: CommandCatalog, width: int) -> str:
    """Render *catalog* as category headings over wrapped command lists.

    Categories and the commands inside each one are sorted alphabetically;
    aliases follow their command in parentheses, e.g. ``upper (up)``.
    """
    blocks = []
    for category in sorted(catalog):
        entries = [
            f"{name} ({', '.join(aliases)})" if aliases else name
            for name, *aliases in sorted(catalog[category])
        ]
        blocks.append(f"  {category}\n" + "\n".join(_wrap_entries(entries, width)))
    return "\n".join(blocks)


def _wrap_entries(entries: list[str], width: int) -> list[str]:
    """Pack comma-separated *entries* into indented lines of at most *width*.

    Unlike ``textwrap``, never breaks inside an entry, so ``html-unescape (hu)``
    stays on one line.  An entry longer than *width* gets a line of its own.
    """
    lines: list[str] = []
    line = ""
    for i, entry in enumerate(entries):
        piece = entry if i == len(entries) - 1 else f"{entry},"
        if line and len(_INDENT) + len(line) + 1 + len(piece) > width:
            lines.append(_INDENT + line)
            line = piece
        else:
            line = f"{line} {piece}" if line else piece
    lines.append(_INDENT + line)
    return lines


def suggest(name: str, catalog: CommandCatalog) -> str | None:
    """Return the command closest to *name*, or ``None`` if nothing is close.

    Uses the same ``difflib.get_close_matches(value, choices, 1)`` call as
    argparse's ``suggest_on_error`` (3.14+).  Aliases are matched too, but the
    suggestion is always the full command name.
    """
    canonical = {alias: cmd[0] for group in catalog.values() for cmd in group for alias in cmd}
    match difflib.get_close_matches(name, canonical, 1):
        case [closest]:
            return canonical[closest]
        case _:
            return None


def exit_unknown_command(
    parser: argparse.ArgumentParser, name: str, catalog: CommandCatalog
) -> NoReturn:
    """Print usage, the error, and the grouped command listing; exit 2."""
    message = f"unknown command {name!r}"
    if (closest := suggest(name, catalog)) is not None:
        message += f", maybe you meant {closest!r}?"
    # Same width rule as argparse's HelpFormatter.
    width = shutil.get_terminal_size().columns - 2
    parser.error(
        f"{message}\n\n"
        "Commands (aliases in parentheses):\n"
        f"{format_catalog(catalog, width)}\n\n"
        f"Run '{parser.prog} <command> --help' for details."
    )
