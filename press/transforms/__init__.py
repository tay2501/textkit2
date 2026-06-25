"""Transform functions — pure, side-effect-free text transformations."""

from __future__ import annotations

import importlib
from typing import Any

# Utility functions not covered by SIMPLE_COMMANDS or PARAMETRIC_COMMANDS
# (internal helpers used by daemon and dict commands, not exposed as CLI subcommands).
_EXTRA: dict[str, tuple[str, str]] = {
    "dict_forward": ("press.transforms.dictionary", "dict_forward"),
    "dict_reverse": ("press.transforms.dictionary", "dict_reverse"),
    "load_tsv": ("press.transforms.dictionary", "load_tsv"),
}


def _build_lazy() -> dict[str, tuple[str, str]]:
    from press.commands import PARAMETRIC_COMMANDS, SIMPLE_COMMANDS

    simple = {cmd.fn: (cmd.module, cmd.fn) for cmd in SIMPLE_COMMANDS}
    parametric = {cmd.fn: (cmd.module, cmd.fn) for cmd in PARAMETRIC_COMMANDS}
    return simple | parametric | _EXTRA


_LAZY = _build_lazy()
__all__ = sorted(_LAZY)


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        mod_name, attr = _LAZY[name]
        mod = importlib.import_module(mod_name)
        value = getattr(mod, attr)
        globals()[name] = value  # cache to avoid repeated __getattr__ calls
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
