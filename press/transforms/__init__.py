"""Transform functions — pure, side-effect-free text transformations."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from press.transforms.case import (
        to_camel_case,
        to_capitalize,
        to_kebab_case,
        to_lower,
        to_pascal_case,
        to_snake_case,
        to_swapcase,
        to_title,
        to_upper,
    )
    from press.transforms.dictionary import dict_forward, dict_reverse, load_tsv
    from press.transforms.encode import base64_decode, base64_encode, url_decode, url_encode
    from press.transforms.encoding_repair import fix_encoding
    from press.transforms.escape import (
        decode_html_entities,
        decode_unicode_escape,
        encode_unicode_escape,
    )
    from press.transforms.json_fmt import json_compress, json_format
    from press.transforms.lineending import to_cr, to_crlf, to_lf
    from press.transforms.lines import dedupe_lines, sort_lines, trim_lines
    from press.transforms.separator import hyphen_to_underscore, underscore_to_hyphen
    from press.transforms.sql import to_sql_in
    from press.transforms.whitespace import normalize_whitespace
    from press.transforms.width import to_fullwidth, to_halfwidth

__all__ = [
    "base64_decode",
    "base64_encode",
    "decode_html_entities",
    "decode_unicode_escape",
    "dedupe_lines",
    "dict_forward",
    "dict_reverse",
    "encode_unicode_escape",
    "fix_encoding",
    "hyphen_to_underscore",
    "json_compress",
    "json_format",
    "load_tsv",
    "normalize_whitespace",
    "sort_lines",
    "to_camel_case",
    "to_capitalize",
    "to_cr",
    "to_crlf",
    "to_fullwidth",
    "to_halfwidth",
    "to_kebab_case",
    "to_lf",
    "to_lower",
    "to_pascal_case",
    "to_snake_case",
    "to_sql_in",
    "to_swapcase",
    "to_title",
    "to_upper",
    "trim_lines",
    "underscore_to_hyphen",
    "url_decode",
    "url_encode",
]

_LAZY: dict[str, tuple[str, str]] = {
    "base64_decode": ("press.transforms.encode", "base64_decode"),
    "base64_encode": ("press.transforms.encode", "base64_encode"),
    "decode_html_entities": ("press.transforms.escape", "decode_html_entities"),
    "decode_unicode_escape": ("press.transforms.escape", "decode_unicode_escape"),
    "dedupe_lines": ("press.transforms.lines", "dedupe_lines"),
    "dict_forward": ("press.transforms.dictionary", "dict_forward"),
    "dict_reverse": ("press.transforms.dictionary", "dict_reverse"),
    "encode_unicode_escape": ("press.transforms.escape", "encode_unicode_escape"),
    "fix_encoding": ("press.transforms.encoding_repair", "fix_encoding"),
    "load_tsv": ("press.transforms.dictionary", "load_tsv"),
    "hyphen_to_underscore": ("press.transforms.separator", "hyphen_to_underscore"),
    "json_compress": ("press.transforms.json_fmt", "json_compress"),
    "json_format": ("press.transforms.json_fmt", "json_format"),
    "normalize_whitespace": ("press.transforms.whitespace", "normalize_whitespace"),
    "sort_lines": ("press.transforms.lines", "sort_lines"),
    "to_camel_case": ("press.transforms.case", "to_camel_case"),
    "to_capitalize": ("press.transforms.case", "to_capitalize"),
    "to_cr": ("press.transforms.lineending", "to_cr"),
    "to_crlf": ("press.transforms.lineending", "to_crlf"),
    "to_fullwidth": ("press.transforms.width", "to_fullwidth"),
    "to_halfwidth": ("press.transforms.width", "to_halfwidth"),
    "to_kebab_case": ("press.transforms.case", "to_kebab_case"),
    "to_lf": ("press.transforms.lineending", "to_lf"),
    "to_lower": ("press.transforms.case", "to_lower"),
    "to_pascal_case": ("press.transforms.case", "to_pascal_case"),
    "to_snake_case": ("press.transforms.case", "to_snake_case"),
    "to_sql_in": ("press.transforms.sql", "to_sql_in"),
    "to_swapcase": ("press.transforms.case", "to_swapcase"),
    "to_title": ("press.transforms.case", "to_title"),
    "to_upper": ("press.transforms.case", "to_upper"),
    "trim_lines": ("press.transforms.lines", "trim_lines"),
    "underscore_to_hyphen": ("press.transforms.separator", "underscore_to_hyphen"),
    "url_decode": ("press.transforms.encode", "url_decode"),
    "url_encode": ("press.transforms.encode", "url_encode"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        mod_name, attr = _LAZY[name]
        mod = importlib.import_module(mod_name)
        value = getattr(mod, attr)
        globals()[name] = value  # cache to avoid repeated __getattr__ calls
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
