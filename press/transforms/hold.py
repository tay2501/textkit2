"""Clipboard hold/release logic for press hold command (Phase 4).

This module provides the file-based toggle used by the CLI.
The daemon uses in-memory state (CommandDispatcher._held_text).
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from press._paths import press_dir

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable
    from pathlib import Path

__all__ = ["hold_path", "toggle_hold_file"]

_HOLD_PATH: Path = press_dir() / "hold.txt"

# Prefix of a DPAPI-encrypted hold file.  Files without it are legacy
# plaintext (pre-encryption releases) and non-Windows test files.
_DPAPI_MAGIC = b"press-dpapi\x00"


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

    Raises:
        RuntimeError: When the hold file cannot be decrypted (written by a
            different user or machine — DPAPI is user-scoped).
    """
    try:
        held = _read_hold_file(path)
        set_text(held)
        path.unlink()
        return False  # released
    except FileNotFoundError:
        text = get_text()
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_hold_file(path, text)
        return True  # held


def _write_hold_file(path: Path, text: str) -> None:
    """Persist *text*, DPAPI-encrypted on Windows.

    Clipboard text can be sensitive, and the hold file lives in ``%APPDATA%``
    where backups and profile sync would otherwise persist it in plaintext.
    Non-Windows (CI/test) keeps the plaintext format — there is no clipboard
    there to hold in the first place.
    """
    if sys.platform == "win32":
        from press._dpapi import protect

        path.write_bytes(_DPAPI_MAGIC + protect(text.encode("utf-8")))
    else:
        path.write_text(text, encoding="utf-8")


def _read_hold_file(path: Path) -> str:
    """Read a hold file written by any press version.

    Current files carry the DPAPI magic prefix; anything else is treated as
    legacy plaintext (pre-encryption releases).  Drop the plaintext fallback
    after one release.
    """
    raw = path.read_bytes()
    if raw.startswith(_DPAPI_MAGIC):
        from press._dpapi import unprotect

        return unprotect(raw[len(_DPAPI_MAGIC) :]).decode("utf-8")
    # Legacy plaintext — re-read in text mode so newline translation matches
    # how write_text() stored it.
    return path.read_text(encoding="utf-8")
