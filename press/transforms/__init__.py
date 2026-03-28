"""Transform functions — pure, side-effect-free text transformations."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from press.transforms.escape import (
        decode_html_entities,
        decode_unicode_escape,
        encode_unicode_escape,
    )
    from press.transforms.lineending import to_cr, to_crlf, to_lf
    from press.transforms.separator import hyphen_to_underscore, underscore_to_hyphen
    from press.transforms.sql import to_sql_in
    from press.transforms.whitespace import normalize_whitespace
    from press.transforms.width import to_fullwidth, to_halfwidth

__all__ = [
    "decode_html_entities",
    "decode_unicode_escape",
    "encode_unicode_escape",
    "hyphen_to_underscore",
    "normalize_whitespace",
    "to_cr",
    "to_crlf",
    "to_fullwidth",
    "to_halfwidth",
    "to_lf",
    "to_sql_in",
    "underscore_to_hyphen",
]

_LAZY: dict[str, tuple[str, str]] = {
    "decode_html_entities": ("press.transforms.escape", "decode_html_entities"),
    "decode_unicode_escape": ("press.transforms.escape", "decode_unicode_escape"),
    "encode_unicode_escape": ("press.transforms.escape", "encode_unicode_escape"),
    "hyphen_to_underscore": ("press.transforms.separator", "hyphen_to_underscore"),
    "normalize_whitespace": ("press.transforms.whitespace", "normalize_whitespace"),
    "to_cr": ("press.transforms.lineending", "to_cr"),
    "to_crlf": ("press.transforms.lineending", "to_crlf"),
    "to_fullwidth": ("press.transforms.width", "to_fullwidth"),
    "to_halfwidth": ("press.transforms.width", "to_halfwidth"),
    "to_lf": ("press.transforms.lineending", "to_lf"),
    "to_sql_in": ("press.transforms.sql", "to_sql_in"),
    "underscore_to_hyphen": ("press.transforms.separator", "underscore_to_hyphen"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        mod_name, attr = _LAZY[name]
        mod = importlib.import_module(mod_name)
        value = getattr(mod, attr)
        globals()[name] = value  # cache to avoid repeated __getattr__ calls
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
