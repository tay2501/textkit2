"""Hash digest generation (hex) over the UTF-8 bytes of the input text."""

from __future__ import annotations

import hashlib


def hash_text(text: str, *, algo: str = "sha256") -> str:
    """Return the hex digest of the UTF-8 encoded *text*.

    The text is hashed exactly as given — line endings are not normalised,
    so CRLF and LF inputs produce different digests (same as ``sha256sum``).

    Args:
        text: Input text.
        algo: Any algorithm accepted by :func:`hashlib.new`
            (e.g. ``sha256``, ``sha1``, ``sha512``, ``md5``).

    Raises:
        ValueError: When *algo* is not a supported algorithm.
    """
    try:
        digest = hashlib.new(algo, text.encode("utf-8"))
    except ValueError as exc:
        available = ", ".join(sorted(hashlib.algorithms_guaranteed))
        raise ValueError(f"unknown hash algorithm {algo!r} (available: {available})") from exc
    return digest.hexdigest()
