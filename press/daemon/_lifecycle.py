"""Daemon lifecycle: singleton mutex, PID/status files, stop/status commands."""

from __future__ import annotations

import ctypes
import sys
from typing import TYPE_CHECKING

from press._paths import press_dir

if TYPE_CHECKING:
    from pathlib import Path

_MUTEX_NAME = "Global\\press_daemon_singleton"

_PID_PATH: Path = press_dir() / "press.pid"
_STATUS_PATH: Path = press_dir() / "status.json"

# Well-known endpoint security/monitoring agent processes (lowercase name →
# product).  Used by ``daemon_status --json`` as a diagnostic: these agents
# hook process launches, file opens, and clipboard operations, which explains
# machine-to-machine speed differences (see docs/user/edr-environments.md).
_KNOWN_MONITORING_AGENTS: dict[str, str] = {
    "msmpeng.exe": "Microsoft Defender AV",
    "mssense.exe": "Microsoft Defender for Endpoint",
    "csfalconservice.exe": "CrowdStrike Falcon",
    "sentinelagent.exe": "SentinelOne",
    "dgagent.exe": "Digital Guardian",
    "dgsvc.exe": "Digital Guardian",
    "edpa.exe": "Symantec DLP",
    "xagt.exe": "Trellix Endpoint (HX)",
    "cylancesvc.exe": "Cylance PROTECT",
    "zsaservice.exe": "Zscaler Client Connector",
}


# ---------------------------------------------------------------------------
# Mutex helpers (Windows only)
# ---------------------------------------------------------------------------


def _mutex_kernel32() -> ctypes.WinDLL:
    """Return kernel32 with mutex prototypes declared.

    ``restype`` must be ``c_void_p`` — the ctypes default of ``c_int``
    truncates 64-bit HANDLEs.  ``use_last_error=True`` because reading
    ``GetLastError()`` through ctypes directly is unreliable (the official
    ctypes docs prescribe :func:`ctypes.get_last_error`).
    """
    import ctypes.wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
    return kernel32


def _acquire_mutex() -> int | None:
    """Acquire the named singleton mutex and return its HANDLE.

    Returns ``None`` when another instance already holds the mutex, or on
    non-Windows platforms.
    """
    if sys.platform == "win32":
        kernel32 = _mutex_kernel32()
        handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            if handle:
                kernel32.CloseHandle(handle)
            return None
        return int(handle) if handle else None
    return None  # pragma: no cover


def _release_mutex(handle: int) -> None:
    """Close the mutex HANDLE."""
    if sys.platform == "win32":
        _mutex_kernel32().CloseHandle(handle)


# ---------------------------------------------------------------------------
# Status file helpers
# ---------------------------------------------------------------------------


def _write_status_file(data: dict[str, object]) -> None:
    """Persist daemon state to *_STATUS_PATH* as JSON."""
    import json

    _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATUS_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _read_status_file() -> dict[str, object] | None:
    """Load the status file, returning ``None`` on missing or parse error."""
    import json

    try:
        return dict(json.loads(_STATUS_PATH.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# stop / status commands
# ---------------------------------------------------------------------------


def stop_daemon() -> int:
    """Send a termination signal to the running daemon.

    Returns:
        0 on success, 1 if the daemon was not running or the PID file was
        missing or stale.
    """
    if not _PID_PATH.exists():
        print("press daemon: not running (no PID file)", file=sys.stderr)
        return 1

    try:
        pid = int(_PID_PATH.read_text(encoding="utf-8").strip())
    except ValueError:
        print("press daemon: error: invalid PID file", file=sys.stderr)
        return 1

    import psutil

    try:
        proc = psutil.Process(pid)
        name = proc.name().lower()
    except psutil.Error:  # NoSuchProcess, or AccessDenied (another user's PID)
        print("press daemon: not running (stale PID file)", file=sys.stderr)
        _PID_PATH.unlink(missing_ok=True)
        return 1

    # PIDs are recycled: a stale file may now point at an unrelated process.
    # Our daemon is either python*.exe (dev) or press.exe (PyInstaller build).
    if not name.startswith(("python", "press")):
        print(
            f"press daemon: not running (PID {pid} belongs to {name!r}; stale PID file)",
            file=sys.stderr,
        )
        _PID_PATH.unlink(missing_ok=True)
        return 1

    try:
        proc.terminate()
        proc.wait(timeout=5)
    except psutil.TimeoutExpired:
        proc.kill()

    _PID_PATH.unlink(missing_ok=True)
    print("press daemon: stopped")
    return 0


def _detect_monitoring_agents() -> list[str]:
    """Return known endpoint monitoring agents currently running (best effort).

    Diagnostic for ``daemon_status --json``: helps users map "press is slow
    on this PC" to the security agent responsible.  Returns an empty list
    when psutil is unavailable (CLI-only install) or enumeration fails.
    """
    try:
        import psutil
    except ImportError:  # pragma: no cover — daemon extra not installed
        return []

    found: set[str] = set()
    import contextlib

    with contextlib.suppress(Exception):
        for proc in psutil.process_iter(["name"]):
            name = str(proc.info.get("name") or "").lower()
            if name in _KNOWN_MONITORING_AGENTS:
                found.add(_KNOWN_MONITORING_AGENTS[name])
    return sorted(found)


def daemon_status(*, as_json: bool = False) -> int:
    """Print the daemon's running status and return an exit code.

    Args:
        as_json: When ``True``, print a JSON object to stdout instead of
            plain text.  The JSON includes ``monitoring_agents`` — known
            endpoint security agents detected on this machine.

    Returns:
        0 if the daemon is running, 1 if not.
    """
    import contextlib

    pid: int | None = None
    if _PID_PATH.exists():
        with contextlib.suppress(ValueError):
            pid = int(_PID_PATH.read_text(encoding="utf-8").strip())

    running = False

    # On Windows: probe the mutex — most reliable indicator
    if sys.platform == "win32":
        probe = _acquire_mutex()
        if probe is None:
            running = True
        else:
            _release_mutex(probe)
    elif pid is not None:
        import psutil

        if psutil.pid_exists(pid):
            running = True
        else:
            _PID_PATH.unlink(missing_ok=True)

    if not as_json:
        if running:
            print(f"press daemon: running (pid={pid or '?'})")
        else:
            print("press daemon: not running")
        return 0 if running else 1

    # JSON output — merge live process data with persisted status file
    import json as _json
    from datetime import UTC

    from press.daemon import _logs

    status = _read_status_file() or {}
    uptime_seconds: int | None = None
    if running and "started_at" in status:
        from datetime import datetime

        with contextlib.suppress(ValueError, TypeError):
            started = datetime.fromisoformat(str(status["started_at"]))
            uptime_seconds = int((datetime.now(UTC) - started.astimezone(UTC)).total_seconds())

    result: dict[str, object] = {
        "running": running,
        "state": "running" if running else str(status.get("state", "stopped")),
        "pid": pid,
        "started_at": status.get("started_at"),
        "uptime_seconds": uptime_seconds,
        "version": status.get("version"),
        "restart_count": int(str(status.get("restart_count", 0))),
        "log_path": str(_logs._LOG_PATH),
        "pid_file": str(_PID_PATH),
        "monitoring_agents": _detect_monitoring_agents(),
    }
    print(_json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if running else 1
