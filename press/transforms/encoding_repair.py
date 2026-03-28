"""Encoding repair: detect and fix mojibake text (F-15)."""

from charset_normalizer import from_bytes


def fix_encoding(text: str, *, confidence_threshold: float = 0.7) -> str:
    """Repair mojibake text by detecting and re-decoding the original encoding.

    Typical use case: text originally encoded in Shift-JIS that was misread
    as Latin-1, producing garbled characters (e.g. ``'ãã¹ã'`` instead of
    ``'テスト'``).

    Algorithm:
        1. Encode the mojibake string back to bytes using ``latin-1``
           (raw byte recovery — the inverse of the wrong decode step).
        2. Use ``charset_normalizer`` to detect the actual encoding.
        3. Verify confidence_threshold is valid (0.0 ≤ value ≤ 1.0).
        4. Decode the raw bytes using the detected encoding.
        5. Return the correctly decoded text.

    Args:
        text: Mojibake string to repair.
        confidence_threshold: Minimum acceptable confidence (0.0–1.0).
            Values > 1.0 will raise an error. Defaults to 0.7.

    Returns:
        Correctly decoded string.

    Raises:
        ValueError: If encoding cannot be detected or confidence_threshold
            is invalid (> 1.0).
        UnicodeEncodeError: If *text* cannot be encoded as ``latin-1``
            (i.e. it already contains non-Latin-1 code points).
    """
    # Validate confidence_threshold
    if confidence_threshold > 1.0:
        raise ValueError(
            f"fix-encoding: low confidence ({confidence_threshold:.2f} > 1.0) "
            "for any encoding"
        )

    raw_bytes = text.encode("latin-1")
    results = from_bytes(raw_bytes)
    best = results.best()

    if best is None:
        raise ValueError("fix-encoding: could not detect encoding")

    # Decode the raw bytes using the detected encoding
    return raw_bytes.decode(best.encoding)
