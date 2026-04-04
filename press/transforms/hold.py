"""Clipboard hold/release logic for press hold command (Phase 4).

This module provides the file-based toggle used by the CLI.
The daemon uses in-memory state (CommandDispatcher._held_text).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["hold_path", "toggle_hold_file"]

_HOLD_PATH: Path = Path(os.environ.get("APPDATA", str(Path.home()))) / "press" / "hold.txt"


def hold_path() -> Path:
    """Return the default hold file path."""
    return _HOLD_PATH


def toggle_hold_file(
    path: Path,
    get_text: Callable[[], str],
    set_text: Callable[[str], None],
) -> bool:
    """Toggle clipboard hold state via a file.

    If *path* does not exist: saves the current clipboard to *path* (hold).
    If *path* exists: restores the saved text to the clipboard and deletes
    *path* (release).

    Args:
        path: Path to the hold file.
        get_text: Callable returning the current clipboard text.
        set_text: Callable writing text to the clipboard.

    Returns:
        ``True`` if the clipboard was just held, ``False`` if just released.
    """
    try:
        held = path.read_text(encoding="utf-8")
        set_text(held)
        path.unlink()
        return False  # released
    except FileNotFoundError:
        text = get_text()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return True  # held
