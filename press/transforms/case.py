"""Case conversion transforms (F-13 to F-21).

Supported conversions:
    F-13  to_snake_case  — camelCase / PascalCase / kebab-case → snake_case
    F-14  to_camel_case  — snake_case / kebab-case / PascalCase → camelCase
    F-15  to_pascal_case — snake_case / kebab-case / camelCase  → PascalCase
    F-16  to_kebab_case  — snake_case / camelCase / PascalCase  → kebab-case
    F-17  to_upper      — Convert all characters to UPPERCASE
    F-18  to_lower      — Convert all characters to lowercase
    F-19  to_title      — Capitalize the first letter of each word (Title Case)
    F-20  to_capitalize — Capitalize the first letter of each line, lowercase rest
    F-21  to_swapcase   — Swap upper and lower case characters
"""

from __future__ import annotations

import re
import string

_RE_UPPER_SEQ = re.compile(r"([A-Z]+)([A-Z][a-z])")
_RE_LOWER_UPPER = re.compile(r"([a-z\d])([A-Z])")
_RE_SPLIT = re.compile(r"[-_\s]+")


def _split_words(text: str) -> list[str]:
    """Split text into a list of lowercase word tokens.

    Handles camelCase, PascalCase, kebab-case, snake_case, and combinations
    such as HTTPSServer or HTTPResponse.

    Args:
        text: A single-word or compound-word string.

    Returns:
        A list of lowercase word strings.
    """
    # Step 1: Handle sequences like "HTTPSServer" → "HTTPS_Server"
    s = _RE_UPPER_SEQ.sub(r"\1_\2", text)
    # Step 2: Handle boundaries like "helloWorld" → "hello_World"
    s = _RE_LOWER_UPPER.sub(r"\1_\2", s)
    # Step 3: Split on hyphens, underscores, and whitespace; discard empty tokens
    return [w.lower() for w in _RE_SPLIT.split(s) if w]


def _convert_line(text: str, joiner: str, capitalize_first: bool, capitalize_rest: bool) -> str:
    """Convert a single line using the given word-join strategy.

    Args:
        text:             A single line of text (no newline character).
        joiner:           String inserted between words (e.g. "_", "-", "").
        capitalize_first: Whether to capitalize the first word.
        capitalize_rest:  Whether to capitalize words after the first.

    Returns:
        The converted line, or the original line if no words were found.
    """
    words = _split_words(text)
    if not words:
        return text
    result: list[str] = []
    for i, word in enumerate(words):
        if i == 0:
            result.append(word.capitalize() if capitalize_first else word)
        else:
            result.append(word.capitalize() if capitalize_rest else word)
    return joiner.join(result)


def _transform_lines(
    text: str,
    joiner: str,
    capitalize_first: bool,
    capitalize_rest: bool,
) -> str:
    """Apply a case conversion to each line of multi-line text.

    Empty lines are preserved as-is.

    Args:
        text:             Multi-line input text.
        joiner:           Separator string between words.
        capitalize_first: Whether to capitalize the first word.
        capitalize_rest:  Whether to capitalize subsequent words.

    Returns:
        Transformed text with the same number of lines as the input.
    """
    lines = text.split("\n")
    converted = [
        _convert_line(line, joiner, capitalize_first, capitalize_rest) if line else ""
        for line in lines
    ]
    return "\n".join(converted)


def to_snake_case(text: str) -> str:
    """Convert each line to snake_case (handles camelCase, PascalCase, kebab-case)."""
    return _transform_lines(text, joiner="_", capitalize_first=False, capitalize_rest=False)


def to_camel_case(text: str) -> str:
    """Convert each line to camelCase."""
    return _transform_lines(text, joiner="", capitalize_first=False, capitalize_rest=True)


def to_pascal_case(text: str) -> str:
    """Convert each line to PascalCase."""
    return _transform_lines(text, joiner="", capitalize_first=True, capitalize_rest=True)


def to_kebab_case(text: str) -> str:
    """Convert each line to kebab-case."""
    return _transform_lines(text, joiner="-", capitalize_first=False, capitalize_rest=False)


def to_upper(text: str) -> str:
    return text.upper()


def to_lower(text: str) -> str:
    return text.lower()


def to_title(text: str) -> str:
    """Convert each line to Title Case using capwords() (handles apostrophes correctly)."""
    return "\n".join(string.capwords(line) if line else "" for line in text.split("\n"))


def to_capitalize(text: str) -> str:
    return "\n".join(line.capitalize() if line else "" for line in text.split("\n"))


def to_swapcase(text: str) -> str:
    return text.swapcase()
