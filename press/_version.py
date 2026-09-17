"""Single source for the installed ``press`` version string.

Kept in its own module rather than in :mod:`press.__main__` so the daemon can
reach it without importing argparse, and so the two failure modes of a damaged
installation are absorbed in one place instead of two divergent ones.
"""

from __future__ import annotations


def press_version() -> str:
    """Return the installed ``press`` version, or ``"unknown"``.

    ``importlib.metadata`` is imported inside the function on purpose: it
    pulls in the email/urllib chain plus a site-packages dist-info scan,
    which the CLI startup budget cannot afford on a run that never asks for
    the version (see ``_LazyVersionAction`` in :mod:`press.__main__`).

    A distribution folder with no ``METADATA`` file fails differently per
    interpreter, and both shapes end up here: Python 3.13/3.14 return
    ``None`` from ``version()``, while Python 3.15 raises
    ``importlib.metadata.MetadataNotFound`` — a ``FileNotFoundError``
    subclass, *not* a ``PackageNotFoundError``, so catching the latter alone
    let it escape as a traceback.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("press") or "unknown"
    except (PackageNotFoundError, OSError):
        return "unknown"
