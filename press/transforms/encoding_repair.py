"""Encoding repair: detect and fix mojibake text (F-15)."""

from charset_normalizer import from_bytes


def fix_encoding(text: str, *, confidence_threshold: float = 0.7) -> str:
    """Repair mojibake by re-encoding to latin-1 bytes then decoding with charset_normalizer.

    Raises ValueError if confidence < threshold or text is not latin-1 encodable.
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
