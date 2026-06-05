"""Transform functions — pure, side-effect-free text transformations."""

from __future__ import annotations

import importlib
from typing import Any

# Parametric / utility functions NOT covered by SIMPLE_COMMANDS.
# SIMPLE_COMMANDS entries are auto-populated by _build_lazy() below.
_EXTRA: dict[str, tuple[str, str]] = {
    "dedupe_lines": ("press.transforms.lines", "dedupe_lines"),
    "dict_forward": ("press.transforms.dictionary", "dict_forward"),
    "dict_reverse": ("press.transforms.dictionary", "dict_reverse"),
    "fix_encoding": ("press.transforms.encoding_repair", "fix_encoding"),
    "json_format": ("press.transforms.json_fmt", "json_format"),
    "load_tsv": ("press.transforms.dictionary", "load_tsv"),
    "sort_lines": ("press.transforms.lines", "sort_lines"),
    "to_sql_in": ("press.transforms.sql", "to_sql_in"),
    "trim_lines": ("press.transforms.lines", "trim_lines"),
}


def _build_lazy() -> dict[str, tuple[str, str]]:
    from press.commands import SIMPLE_COMMANDS  # lightweight: dataclasses only

    return {cmd.fn: (cmd.module, cmd.fn) for cmd in SIMPLE_COMMANDS} | _EXTRA


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
