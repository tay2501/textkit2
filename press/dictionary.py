"""Dictionary file management for press (F-08, F-09)."""

import os
import sys
from pathlib import Path

from press.transforms.dictionary import load_tsv

__all__ = ["add_entry", "default_dict_path", "list_entries", "remove_entry"]


def default_dict_path() -> Path:
    """Return the default dictionary file path.

    On Windows, returns ``%APPDATA%/press/dict/default.tsv``.
    On other platforms, returns ``~/.config/press/dict/default.tsv``.

    Returns:
        Absolute path to the default TSV dictionary file.
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "press" / "dict" / "default.tsv"


def list_entries(path: Path) -> list[tuple[str, str]]:
    """Return all (key, value) pairs from the TSV file.

    Args:
        path: Path to the TSV file.

    Returns:
        List of (key, value) tuples in file order.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    table = load_tsv(path)
    return list(table.items())


def add_entry(key: str, value: str, path: Path) -> None:
    """Append a key/value entry to the TSV file.

    Creates the file (and any parent directories) if they do not exist.

    Args:
        key: Dictionary key to add.
        value: Corresponding value.
        path: Path to the TSV file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{key}\t{value}\n")


def remove_entry(key: str, path: Path) -> bool:
    """Remove the entry with the given key from the TSV file.

    Non-data lines (comments, blank lines) are preserved. Only the first
    occurrence of a matching key is removed.

    Args:
        key: Key to remove.
        path: Path to the TSV file.

    Returns:
        True if an entry was removed, False if the key was not found.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Dictionary file not found: {path}")

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines: list[str] = []
    removed = False

    for line in lines:
        stripped = line.strip()
        # Preserve comments and blank lines unconditionally
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        parts = stripped.split("\t")
        if not removed and len(parts) >= 1 and parts[0] == key:
            removed = True  # skip this line (effectively removes it)
        else:
            new_lines.append(line)

    if removed:
        path.write_text("".join(new_lines), encoding="utf-8")

    return removed
