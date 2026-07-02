"""Shared filesystem locations for press data files.

All press state (config, hold file, daemon PID/log/status) lives under
``%APPDATA%\\press``.  On platforms without an ``APPDATA`` environment
variable (non-Windows CI/test runs), the user's home directory is the base.

These helpers read the environment on each call, but some consumers
(``press.daemon``, ``press.transforms.hold``) capture the result in
module-level constants at import time — tests monkeypatch those constants
directly rather than ``APPDATA``.

The CLI dictionary default is the exception to the ``%APPDATA%`` rule:
:func:`press.dictionary.default_dict_path` deliberately follows platform
conventions (``AppData/Roaming`` / XDG) instead of these helpers.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["appdata_dir", "press_dir"]


def appdata_dir() -> Path:
    """Return ``%APPDATA%`` as a Path, falling back to the home directory."""
    return Path(os.environ.get("APPDATA", str(Path.home())))


def press_dir() -> Path:
    """Return the press data directory (``%APPDATA%\\press``)."""
    return appdata_dir() / "press"
