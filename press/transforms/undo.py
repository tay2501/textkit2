"""Undo — restore the clipboard text press overwrote.

File-based single-slot snapshot used by the CLI.  The daemon keeps its own
in-memory slot (``CommandDispatcher``) — the same dual-layer design as hold.
The snapshot file shares hold's on-disk format (DPAPI-encrypted on Windows).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from press._paths import press_dir
from press.transforms.hold import _read_hold_file, _write_hold_file

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

__all__ = ["save_snapshot", "snapshot_allowed", "swap_undo", "undo_disabled", "undo_path"]


def undo_path() -> Path:
    """Return the undo snapshot file path."""
    return press_dir() / "undo.txt"


def undo_disabled() -> bool:
    """True when the user opted out via ``PRESS_NO_UNDO=1``.

    An environment variable rather than config.toml so the CLI transform
    path never has to read the config file (EDR file-open budget), matching
    the ``PRESS_NO_DAEMON`` precedent.
    """
    return os.environ.get("PRESS_NO_UNDO", "") not in ("", "0")


def snapshot_allowed() -> bool:
    """Whether press may keep the clipboard text it is about to overwrite.

    One rule, two slots: the CLI writes a file (``_snapshot_clipboard_for_undo``)
    and the daemon keeps an in-memory slot (``CommandDispatcher._remember_for_undo``),
    but both decline for the same three reasons — the user opted out with
    ``PRESS_NO_UNDO=1``, the content carries the sensitive-exclusion formats
    (a genpass password, a KeePassXC copy), or the marks cannot be read at
    all, in which case not keeping it is the safe answer.
    """
    if undo_disabled():
        return False
    try:
        from press.clipboard import clipboard_has_sensitive_marks

        return not clipboard_has_sensitive_marks()
    except (OSError, RuntimeError):
        return False


def save_snapshot(text: str) -> None:
    """Persist *text* as the undo slot (DPAPI-encrypted on Windows)."""
    path = undo_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_hold_file(path, text)


def swap_undo(get_text: Callable[[], str], set_text: Callable[[str], None]) -> None:
    """Swap the clipboard with the undo slot (running undo twice = redo).

    Args:
        get_text: Callable returning the current clipboard text.
        set_text: Callable writing text to the clipboard.

    Raises:
        FileNotFoundError: When no undo snapshot exists.
        RuntimeError: When the snapshot cannot be decrypted (DPAPI is
            user-scoped) or the clipboard write fails.
    """
    path = undo_path()
    saved = _read_hold_file(path)
    try:
        current = get_text()
    except (OSError, RuntimeError):
        # Empty / non-text clipboard: the redo slot becomes empty text.
        current = ""
    set_text(saved)
    _write_hold_file(path, current)
