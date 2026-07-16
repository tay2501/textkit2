"""Unix time ⇔ ISO 8601 date conversion (applied per line)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# Unix-time magnitudes at or above this are treated as milliseconds
# (100_000_000_000 s ≈ year 5138, while current epoch ms ≈ 1.7e12).
_MS_THRESHOLD = 100_000_000_000


def _map_lines(text: str, fn: Callable[[str], str]) -> str:
    """Apply *fn* to each non-blank line; blank lines and trailing newline pass through."""
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(fn(line.strip()) if line.strip() else line for line in normalised.split("\n"))


def unix_to_date(text: str, *, utc: bool = False) -> str:
    """Convert Unix timestamps (one per line) to ISO 8601 dates.

    Seconds vs. milliseconds is auto-detected by magnitude.  Output is local
    time with UTC offset by default; ``utc=True`` outputs UTC.

    Raises:
        ValueError: When a non-blank line is not a number.
    """

    def _one(token: str) -> str:
        try:
            value = float(token)
        except ValueError as exc:
            raise ValueError(f"not a unix timestamp: {token!r}") from exc
        if abs(value) >= _MS_THRESHOLD:
            value /= 1000.0
        dt = datetime.fromtimestamp(value, tz=UTC)
        spec = "seconds" if dt.microsecond == 0 else "milliseconds"
        target = dt if utc else dt.astimezone()
        return target.isoformat(timespec=spec)

    return _map_lines(text, _one)


def date_to_unix(text: str, *, ms: bool = False) -> str:
    """Convert ISO 8601 dates (one per line) to Unix time in seconds.

    Dates without a UTC offset are interpreted as local time.  ``ms=True``
    outputs milliseconds instead of seconds.

    Raises:
        ValueError: When a non-blank line is not an ISO 8601 date.
    """

    def _one(token: str) -> str:
        try:
            dt = datetime.fromisoformat(token)
        except ValueError as exc:
            raise ValueError(f"not an ISO 8601 date: {token!r}") from exc
        if dt.tzinfo is None:
            dt = dt.astimezone()
        if ms:
            return str(round(dt.timestamp() * 1000))
        ts = dt.timestamp()
        return str(int(ts)) if ts.is_integer() else str(ts)

    return _map_lines(text, _one)
