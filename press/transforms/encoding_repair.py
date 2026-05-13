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
        3. Compute confidence as ``1.0 - best.chaos`` (chaos=0.0 means perfect).
        4. If confidence >= *confidence_threshold*, return the decoded text.
        5. Otherwise raise :exc:`ValueError`.

    Args:
        text: Mojibake string to repair.
        confidence_threshold: Minimum confidence to accept (0.0–1.0, default 0.7).
            ``confidence = 1.0 - chaos``, where ``chaos`` is the ratio of
            unexpected characters detected by charset_normalizer.

    Returns:
        Correctly decoded string.

    Raises:
        ValueError: If encoding cannot be detected, confidence is below
            *confidence_threshold*, or *text* contains characters outside
            the latin-1 range (i.e. it is already correctly decoded, not mojibake).
    """
    try:
        raw_bytes = text.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "fix-encoding: input is not mojibake (contains non-latin-1 characters)"
        ) from exc
    results = from_bytes(raw_bytes)
    best = results.best()

    if best is None:
        raise ValueError("fix-encoding: could not detect encoding")

    confidence = 1.0 - best.chaos
    if confidence < confidence_threshold:
        raise ValueError(
            f"fix-encoding: low confidence ({confidence:.2f} < {confidence_threshold}) "
            f"for detected encoding '{best.encoding}'"
        )

    return raw_bytes.decode(best.encoding)
