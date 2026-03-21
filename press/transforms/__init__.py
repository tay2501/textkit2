"""Transform functions — pure, side-effect-free text transformations."""

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
