"""URL slug generation (Django-style slugify)."""

from __future__ import annotations

import re
import unicodedata


def slugify(text: str, *, unicode: bool = False) -> str:
    """Convert *text* to a URL slug: lowercase, hyphen-separated, trimmed.

    By default the text is ASCII-folded via NFKD — accents are stripped
    (``Café`` → ``cafe``) and characters with no ASCII equivalent are
    dropped.  With ``unicode=True`` non-ASCII word characters are kept
    (NFKC-normalised) for Japanese or other non-Latin slugs.
    """
    if unicode:
        value = unicodedata.normalize("NFKC", text)
    else:
        value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")
