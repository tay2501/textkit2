"""File-based clipboard stash for ``press stash`` (push / pop / drop / list).

A single slot in ``%APPDATA%\\press\\stash.txt``, named after ``git stash``:
it saves text for later and restores it on request.  It does not protect the
clipboard — that is the daemon's ClipboardGuard (hotkey ``h``,``o``, kept
in memory by ``CommandDispatcher``).

The slot file format is shared with the undo snapshot (:mod:`.undo`).
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from press._paths import press_dir

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable
    from pathlib import Path

__all__ = ["drop", "pop", "push", "stash_path", "stashed"]

_STASH_PATH: Path = press_dir() / "stash.txt"

# Prefixes of a DPAPI-encrypted slot file.  The second one records that the
# text carried the clipboard's sensitive-exclusion formats (a genpass
# password), so a restore can mark it again.  Files with neither prefix are
# legacy plaintext (pre-encryption releases) and non-Windows test files.
_DPAPI_MAGIC = b"press-dpapi\x00"
_DPAPI_SENSITIVE_MAGIC = b"press-dpapi-sensitive\x00"


def stash_path() -> Path:
    """Return the default stash file path."""
    return _STASH_PATH


def push(path: Path, text: str, *, sensitive: bool) -> None:
    """Save *text* to the stash at *path*.

    Raises:
        FileExistsError: When a stash already exists — there is one slot,
            and replacing it silently would lose the saved text.
    """
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_slot_file(path, text, sensitive=sensitive)


def pop(path: Path, set_text: Callable[[str, bool], None]) -> None:
    """Restore the stash through ``set_text(text, sensitive)``, then delete it.

    The file is deleted only after the restore succeeded, so a clipboard
    failure leaves the stash in place.

    Raises:
        FileNotFoundError: When nothing is stashed.
        RuntimeError: When the file cannot be decrypted or is not UTF-8.
    """
    text, sensitive = read_slot_file(path)
    set_text(text, sensitive)
    path.unlink()


def drop(path: Path) -> None:
    """Delete the stash without restoring it.

    Raises:
        FileNotFoundError: When nothing is stashed.
    """
    path.unlink()


def stashed(path: Path) -> tuple[str, bool]:
    """Return ``(text, sensitive)`` of the stash without changing it.

    Raises:
        FileNotFoundError: When nothing is stashed.
    """
    return read_slot_file(path)


def write_slot_file(path: Path, text: str, *, sensitive: bool = False) -> None:
    """Persist *text*, DPAPI-encrypted on Windows.

    Clipboard text can be sensitive, and the file lives in ``%APPDATA%``
    where backups and profile sync would otherwise persist it in plaintext.
    Non-Windows (CI/test) keeps the plaintext format — there is no clipboard
    there to save in the first place.
    """
    if sys.platform == "win32":
        from press._dpapi import protect

        magic = _DPAPI_SENSITIVE_MAGIC if sensitive else _DPAPI_MAGIC
        path.write_bytes(magic + protect(text.encode("utf-8")))
    else:
        path.write_text(text, encoding="utf-8")


def read_slot_file(path: Path) -> tuple[str, bool]:
    """Read a slot file written by any press version.

    Returns:
        ``(text, sensitive)``.

    Raises:
        RuntimeError: When the file cannot be decrypted, or holds bytes that
            are not valid UTF-8.
    """
    raw = path.read_bytes()
    try:
        for magic, sensitive in ((_DPAPI_MAGIC, False), (_DPAPI_SENSITIVE_MAGIC, True)):
            if raw.startswith(magic):
                from press._dpapi import unprotect

                return unprotect(raw[len(magic) :]).decode("utf-8"), sensitive
        # Legacy plaintext — re-read in text mode so newline translation
        # matches how write_text() stored it.  Drop after one release.
        return path.read_text(encoding="utf-8"), False
    except UnicodeDecodeError as exc:
        # The stash and undo handlers report OSError and RuntimeError; a file
        # that is not UTF-8 is a corrupt file, not a bug, so it joins them
        # instead of escaping the handler as a traceback.
        raise RuntimeError(f"stash file is not valid UTF-8: {path}") from exc
