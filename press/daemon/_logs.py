"""Daemon logging setup and the ``daemon logs`` command implementation."""

from __future__ import annotations

import contextlib
import logging
import re
import sys
import time
from typing import TYPE_CHECKING

from press._paths import press_dir, trace_path

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_LOG_PATH: Path = press_dir() / "daemon.log"
_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per SPEC §15
_LOG_BACKUP_COUNT = 3

# Module-level logger — handlers are added by _setup_logging() at daemon start.
_log = logging.getLogger("press.daemon")

# Log line format written by _setup_logging's Formatter:
#   2026-05-15T09:30:00 INFO     message text here
_LOG_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")
_LEVEL_MIN: dict[str, int] = {
    "debug": 10,
    "info": 20,
    "warning": 30,
    "error": 40,
    "critical": 50,
    "all": 0,
}


def refresh_level() -> None:
    """Set the daemon logger's level from the ``press trace`` marker file.

    DEBUG when ``%APPDATA%\\press\\trace`` exists (``press trace on``), INFO
    otherwise.  A single ``os.path.exists()`` stat, cheap enough to call once
    per dispatched action (see ``CommandDispatcher``) so toggling the marker
    takes effect on the very next action without a daemon restart.
    """
    _log.setLevel(logging.DEBUG if trace_path().exists() else logging.INFO)


@contextlib.contextmanager
def timed(label: str, **fields: object) -> Iterator[None]:
    """Log *label*'s elapsed time at DEBUG, or do nothing when DEBUG is off.

    Standard "check isEnabledFor before doing the work" idiom from the
    CPython logging HOWTO's Optimization section — skips the
    ``time.perf_counter()`` calls entirely on the hot path when tracing is
    off (the default).

    Security: *fields* must only ever carry counts, command names, or byte
    counts (e.g. ``chars=N``, ``cmd="upper"``) — never clipboard body text or
    dictionary entry contents.
    """
    if not _log.isEnabledFor(logging.DEBUG):
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        extra = " ".join(f"{key}={value}" for key, value in fields.items())
        message = f"{label} elapsed_ms={elapsed_ms:.2f}"
        if extra:
            message = f"{message} {extra}"
        _log.debug(message)


def _setup_logging() -> None:
    """Configure rotating file logging for the daemon (idempotent)."""
    import logging.handlers

    if _log.handlers:
        return
    refresh_level()
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        _LOG_PATH,
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    _log.addHandler(handler)


def daemon_logs(
    lines: int | None = 50,
    *,
    follow: bool = False,
    level: str = "all",
    as_json: bool = False,
) -> int:
    """Print entries from the daemon log file.

    Args:
        lines: Number of tail lines to show, or ``None`` to show all.
        follow: If ``True``, stream new entries until Ctrl+C.
        level: Minimum level to display (``debug``/``info``/``warning``/``error``/``all``).
        as_json: Emit one JSON object per line (NDJSON) instead of plain text.

    Returns:
        0 on success, 1 if the log file does not exist.
    """
    import json as _json
    import time

    if not _LOG_PATH.exists():
        print(f"press daemon: log file not found: {_LOG_PATH}", file=sys.stderr)
        print("press daemon: start the daemon first to create a log file", file=sys.stderr)
        return 1

    min_level = _LEVEL_MIN.get(level.lower(), 0)

    def _parse(raw: str) -> tuple[str, str, str] | None:
        m = _LOG_LINE_RE.match(raw.rstrip("\n\r"))
        if not m:
            return None
        return m.group(1), m.group(2), m.group(3)

    def _passes(lvl: str) -> bool:
        return _LEVEL_MIN.get(lvl.lower(), 0) >= min_level

    def _emit(ts: str, lvl: str, msg: str) -> None:
        if as_json:
            print(_json.dumps({"ts": ts, "level": lvl, "msg": msg}))
        else:
            print(f"{ts} {lvl:<8} {msg}")

    with _LOG_PATH.open(encoding="utf-8", errors="replace") as fh:
        all_lines = fh.readlines()

    tail = all_lines[-lines:] if lines is not None else all_lines
    for raw in tail:
        parsed = _parse(raw)
        if parsed and _passes(parsed[1]):
            _emit(*parsed)

    if not follow:
        return 0

    print(f"Following {_LOG_PATH} — press Ctrl+C to stop", file=sys.stderr)
    try:
        with _LOG_PATH.open(encoding="utf-8", errors="replace") as fh:
            fh.seek(0, 2)  # jump to end
            while True:
                raw = fh.readline()
                if raw:
                    parsed = _parse(raw)
                    if parsed and _passes(parsed[1]):
                        _emit(*parsed)
                        sys.stdout.flush()
                else:
                    time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    return 0
