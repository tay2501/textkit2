"""Declarative registry of simple transform commands.

A "simple" command maps 1-to-1 onto a pure transform function that accepts
only ``text: str`` and returns ``str`` — no extra parameters beyond the
standard I/O flags added by ``_add_io_args()``.

Parametric commands that need extra CLI arguments are excluded:
- ``sql-in``      (--quote-char, --wrap)
- ``fix-encoding``  (--threshold)
- ``json-format``   (--indent)

This module is imported by both ``__main__.py`` (CLI registration) and
``daemon.py`` (hotkey dispatch), making it the single source of truth for
all simple transform commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SimpleCommand:
    """Metadata for one simple (no-extra-args) transform command."""

    name: str
    module: str
    fn: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    help: str = ""


# fmt: off
SIMPLE_COMMANDS: tuple[SimpleCommand, ...] = (
    # --- width ---
    SimpleCommand("halfwidth",      "press.transforms.width",      "to_halfwidth",          ("hw",),   "Convert full-width characters to half-width"),
    SimpleCommand("fullwidth",      "press.transforms.width",      "to_fullwidth",          ("fw",),   "Convert half-width characters to full-width"),
    # --- whitespace ---
    SimpleCommand("normalize",      "press.transforms.whitespace", "normalize_whitespace",  ("norm",), "Normalize whitespace and blank lines"),
    # --- line endings ---
    SimpleCommand("crlf",           "press.transforms.lineending", "to_crlf",               (),        r"Convert line endings to CRLF (\r\n)"),
    SimpleCommand("lf",             "press.transforms.lineending", "to_lf",                 (),        r"Convert line endings to LF (\n)"),
    SimpleCommand("cr",             "press.transforms.lineending", "to_cr",                 (),        r"Convert line endings to CR (\r)"),
    # --- separator ---
    SimpleCommand("underscore",     "press.transforms.separator",  "hyphen_to_underscore",  ("us",),   "Convert hyphens to underscores"),
    SimpleCommand("hyphen",         "press.transforms.separator",  "underscore_to_hyphen",  ("hy",),   "Convert underscores to hyphens"),
    # --- escape ---
    SimpleCommand("unicode-decode", "press.transforms.escape",     "decode_unicode_escape", ("ud",),   r"Decode \uXXXX escape sequences to text"),
    SimpleCommand("unicode-encode", "press.transforms.escape",     "encode_unicode_escape", ("ue",),   r"Encode text to \uXXXX escape sequences"),
    SimpleCommand("html-decode",    "press.transforms.escape",     "decode_html_entities",  ("hd",),   "Decode HTML entities (e.g. &amp; → &)"),
    # --- case ---
    SimpleCommand("snake",          "press.transforms.case",       "to_snake_case",         ("sn",),   "Convert to snake_case"),
    SimpleCommand("camel",          "press.transforms.case",       "to_camel_case",         ("cm",),   "Convert to camelCase"),
    SimpleCommand("pascal",         "press.transforms.case",       "to_pascal_case",        ("pc",),   "Convert to PascalCase"),
    SimpleCommand("kebab",          "press.transforms.case",       "to_kebab_case",         ("kb",),   "Convert to kebab-case"),
    SimpleCommand("upper",          "press.transforms.case",       "to_upper",              ("up",),   "Convert all characters to UPPERCASE"),
    SimpleCommand("lower",          "press.transforms.case",       "to_lower",              ("lo",),   "Convert all characters to lowercase"),
    SimpleCommand("title",          "press.transforms.case",       "to_title",              ("tt",),   "Capitalize the first letter of each word (Title Case)"),
    SimpleCommand("capitalize",     "press.transforms.case",       "to_capitalize",         ("cap",),  "Capitalize the first letter of each line, lowercase rest"),
    SimpleCommand("swapcase",       "press.transforms.case",       "to_swapcase",           ("sw",),   "Swap upper and lower case characters"),
    # --- encode ---
    SimpleCommand("base64-encode",  "press.transforms.encode",     "base64_encode",         ("be",),   "Encode text to Base64"),
    SimpleCommand("base64-decode",  "press.transforms.encode",     "base64_decode",         ("bd",),   "Decode Base64 to text"),
    SimpleCommand("url-encode",     "press.transforms.encode",     "url_encode",            ("ue2",),  "Percent-encode URL text"),
    SimpleCommand("url-decode",     "press.transforms.encode",     "url_decode",            ("ud2",),  "Decode percent-encoded URL text"),
    # --- json ---
    SimpleCommand("json-compress",  "press.transforms.json_fmt",   "json_compress",         ("jc",),   "Compress JSON to single line"),
)
# fmt: on

# O(1) lookup by command name — used by daemon.CommandDispatcher._transform()
SIMPLE_COMMAND_INDEX: dict[str, SimpleCommand] = {cmd.name: cmd for cmd in SIMPLE_COMMANDS}
