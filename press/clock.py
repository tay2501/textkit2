"""Current date/time formatting for the ``date`` and ``time`` commands.

Formats are :meth:`datetime.datetime.strftime` strings — the syntax of GNU
``date +FORMAT``, Espanso's date extension, and Starship's ``time_format`` —
so ``%Y-%m-%d`` is what other tools call ``YYYY-MM-DD``.  ``strftime``
delegates to the platform C library, which is why a format is checked by
actually running it (:func:`check_format`) rather than against an allow-list:
Windows rejects ``%-d`` and ``%Q`` with ``ValueError`` while glibc passes them
through.

Like :mod:`press.genpass`, this is a generator rather than a transform: it
ignores its input, so it lives outside :mod:`press.transforms`.
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = [
    "DEFAULT_DATE_FORMAT",
    "DEFAULT_TIME_FORMAT",
    "check_format",
    "format_configured",
    "format_now",
]

DEFAULT_DATE_FORMAT = "%Y%m%d"
DEFAULT_TIME_FORMAT = "%H%M%S"

# Fixed instant for validation, so checking a format never depends on the clock.
_PROBE = datetime(2000, 1, 2, 3, 4, 5, tzinfo=UTC)


def check_format(fmt: object) -> str:
    """Return *fmt* if it is a usable strftime format, else raise ``ValueError``.

    Rejects non-strings, the empty string (it would write an empty clipboard),
    NUL (CF_UNICODETEXT is NUL-terminated, so the clipboard would hold less
    than stdout prints), and directives the running platform's ``strftime``
    refuses.

    Raises:
        ValueError: With a message naming the problem.
    """
    if not isinstance(fmt, str):
        raise ValueError(f"format must be a string, got {type(fmt).__name__}")
    if not fmt:
        raise ValueError("format is empty")
    if "\0" in fmt:
        raise ValueError("format contains a NUL character")
    try:
        _PROBE.strftime(fmt)
    except ValueError as exc:
        raise ValueError(f"invalid format {fmt!r}: {exc}") from exc
    return fmt


def format_now(fmt: str, *, utc: bool = False, now: datetime | None = None) -> str:
    """Return the current local time (or UTC) formatted with *fmt*.

    Args:
        fmt: A strftime format, e.g. ``"%Y%m%d"``.
        utc: Format in UTC instead of local time (``date -u``).
        now: The instant to format, used as-is unless *utc* converts it;
            ``None`` reads the clock.  Tests inject it.

    Raises:
        ValueError: When *fmt* is not a usable format (see :func:`check_format`).
    """
    check_format(fmt)
    if now is None:
        now = datetime.now(UTC) if utc else datetime.now().astimezone()
    return (now.astimezone(UTC) if utc else now).strftime(fmt)


def format_configured(section: str, fmt: str, *, utc: bool = False) -> str:
    """:func:`format_now` for a format read from ``config.toml``.

    The config loader keeps an unusable ``[date]``/``[time]`` format instead of
    failing — one bad key must not stop the daemon and every other hotkey — so
    the error surfaces here, when the command is used, naming the key to fix.

    Raises:
        ValueError: ``"[<section>] format: <reason>"``.
    """
    try:
        return format_now(fmt, utc=utc)
    except ValueError as exc:
        raise ValueError(f"[{section}] format in config.toml: {exc}") from exc
