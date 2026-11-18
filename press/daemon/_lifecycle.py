"""Daemon lifecycle: singleton mutex, PID/status files, stop/status commands."""

from __future__ import annotations

import contextlib
import ctypes
import sys
from typing import TYPE_CHECKING

from press._paths import press_dir
from press._pipe import _load_kernel32, user_name

if TYPE_CHECKING:
    import subprocess
    from pathlib import Path

    import psutil

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


_ERROR_ALREADY_EXISTS = 183
_WAIT_OBJECT_0 = 0x0
_WAIT_ABANDONED = 0x80


def _mutex_name() -> str:
    """Return the per-user name of the daemon singleton mutex.

    Per-user, like the pipe name and the PID file: a machine-wide name would
    let one user's daemon (or a deliberately squatted mutex) block every other
    user's daemon on a shared machine.  Derivation shared with
    :func:`press._pipe.pipe_name` via :func:`press._pipe.user_name` and, like
    it, resolved per call (test_pipe.py pins the two together).
    """
    return f"Global\\press_daemon_singleton_{user_name()}"


def _acquire_mutex(timeout_ms: int = 0) -> int | None:
    """Acquire the named singleton mutex and return its HANDLE.

    Uses the shared Win32 loader (:func:`press._pipe._load_kernel32`), which
    declares ``CreateMutexW``/``CloseHandle`` with ``c_void_p`` HANDLEs (the
    ctypes default of ``c_int`` truncates 64-bit handles) and loads kernel32
    with ``use_last_error=True`` so :func:`ctypes.get_last_error` is reliable.

    When the name already exists, ``bInitialOwner`` is ignored: another
    handle keeps the mutex alive — a running daemon, or only a ``status`` /
    ``stop`` probe about to release it.  Waiting up to *timeout_ms* tells the
    two apart, so a daemon starting next to a probe does not give up.  A Win32
    mutex is recursive, so a thread that already owns it acquires it again.

    Returns ``None`` when another owner keeps the mutex, or on non-Windows
    platforms.
    """
    if sys.platform == "win32":
        kernel32 = _load_kernel32()
        handle = kernel32.CreateMutexW(None, True, _mutex_name())
        if not handle:
            return None
        if ctypes.get_last_error() != _ERROR_ALREADY_EXISTS:
            return int(handle)
        # WAIT_ABANDONED: the previous owner died holding it; ownership is ours.
        if kernel32.WaitForSingleObject(handle, timeout_ms) in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
            return int(handle)
        kernel32.CloseHandle(handle)
        return None
    return None  # pragma: no cover


def _release_mutex(handle: int) -> None:
    """Release ownership, then close the mutex HANDLE.

    Closing alone does not release: while another handle keeps the mutex
    alive (a daemon waiting in :func:`_acquire_mutex`), it would stay owned
    by this thread until the thread exits.
    """
    if sys.platform == "win32":
        kernel32 = _load_kernel32()
        kernel32.ReleaseMutex(handle)  # fails harmlessly when not the owner
        kernel32.CloseHandle(handle)


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


def _read_pid() -> int | None:
    """Return the PID recorded in the PID file, or ``None`` if missing/invalid."""
    try:
        return int(_PID_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _probe_running(pid: int | None) -> bool:
    """Return whether a daemon is running, removing a PID file proven stale.

    On Windows the singleton mutex decides — the most reliable indicator.  Its
    holder may not have written its PID file yet (``run_daemon`` takes the
    mutex first and writes the PID once the tray is up), so a ``True`` here
    with no PID is a daemon still starting.
    """
    if sys.platform == "win32":
        probe = _acquire_mutex()
        if probe is None:
            return True
        # Holding the mutex proves no daemon is running, and none can be
        # between its own mutex acquisition and PID write, so a leftover PID
        # file is stale.  Remove it *before* releasing: every CLI run otherwise
        # pays the delegation imports (~14 file opens) for a daemon that is
        # gone.  Best effort: a file locked by another process must not break
        # the caller.
        try:
            with contextlib.suppress(OSError):
                _PID_PATH.unlink(missing_ok=True)
        finally:
            _release_mutex(probe)
        return False
    if pid is None:
        return False
    import psutil

    if psutil.pid_exists(pid):
        return True
    with contextlib.suppress(OSError):
        _PID_PATH.unlink(missing_ok=True)
    return False


def _daemon_process(pid: int) -> psutil.Process | None:
    """Return the process behind *pid* if it can be our daemon, else ``None``."""
    import psutil

    try:
        proc = psutil.Process(pid)
        name = proc.name().lower()
    except psutil.Error:  # NoSuchProcess, or AccessDenied (another user's PID)
        return None
    # PIDs are recycled: a stale file may now point at an unrelated process.
    # Our daemon is either python*.exe (dev) or press.exe (PyInstaller build).
    return proc if name.startswith(("python", "press")) else None


def stop_daemon() -> int:
    """Terminate the running daemon (idempotent, like ``systemctl stop``).

    Returns:
        0 when the daemon was stopped or was not running; 1 when a daemon is
        running but cannot be stopped (still starting, PID file not pointing
        at it, or termination refused).
    """
    pid = _read_pid()
    if not _probe_running(pid):
        print("press daemon: not running")
        return 0
    if pid is None:
        print(
            "press daemon: error: the daemon has not written its PID file yet; try again",
            file=sys.stderr,
        )
        return 1

    import psutil

    if (proc := _daemon_process(pid)) is None:
        print(
            f"press daemon: error: PID {pid} in the PID file is not the running daemon; try again",
            file=sys.stderr,
        )
        return 1

    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except psutil.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    except psutil.NoSuchProcess:
        pass  # exited on its own meanwhile
    except (psutil.AccessDenied, psutil.TimeoutExpired) as exc:
        print(f"press daemon: error: could not stop PID {pid}: {exc}", file=sys.stderr)
        return 1

    with contextlib.suppress(OSError):
        _PID_PATH.unlink(missing_ok=True)
    print("press daemon: stopped")
    return 0


# Readiness wait: EDR-monitored PCs can take several seconds to import the
# daemon's dependencies on first run.
_START_TIMEOUT = 15.0
_START_POLL = 0.1
_STDERR_LOG_PATH: Path = press_dir() / "daemon-stderr.log"
_STDERR_TAIL_LINES = 20
_DAEMON_MODULES = ("pystray", "pynput", "PIL", "psutil")


def _missing_daemon_modules() -> list[str]:
    """Return the ``daemon`` extra's modules this interpreter cannot import."""
    if getattr(sys, "frozen", False):
        return []  # the PyInstaller build bundles them
    from importlib.util import find_spec

    return [name for name in _DAEMON_MODULES if find_spec(name) is None]


def _daemon_argv() -> list[str]:
    """Return the command line that runs the daemon in the foreground."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "daemon", "run"]
    # -P: never put the current directory on sys.path — a press/ folder there
    # would otherwise run as the daemon instead of the installed package.
    return [sys.executable, "-P", "-m", "press", "daemon", "run"]


def _spawn_daemon() -> subprocess.Popen[bytes]:
    """Start ``press daemon run`` as a windowless background process.

    ``CREATE_NO_WINDOW``, not ``DETACHED_PROCESS``: under a venv/uv install
    ``sys.executable`` is a launcher that starts the real interpreter, and a
    detached launcher makes Windows give that interpreter a new, visible
    console.  ``CREATE_NEW_PROCESS_GROUP`` keeps the terminal's Ctrl+C away
    from the daemon.  Breakaway lets it outlive a job that kills its members
    when the terminal closes; a job that forbids breakaway refuses the flag
    with ERROR_ACCESS_DENIED, and the daemon then starts inside it.

    stderr goes to :data:`_STDERR_LOG_PATH` so a start-up crash before
    logging is set up still leaves its traceback.  The working directory is
    fixed so the daemon never pins the directory ``start`` was run from.
    """
    if sys.platform != "win32":
        raise OSError("the daemon requires Windows")
    import subprocess

    home = press_dir()
    home.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    with _STDERR_LOG_PATH.open("wb") as stderr:

        def _popen(creationflags: int) -> subprocess.Popen[bytes]:
            return subprocess.Popen(
                _daemon_argv(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                cwd=home,
                creationflags=creationflags,
            )

        try:
            return _popen(flags | subprocess.CREATE_BREAKAWAY_FROM_JOB)
        except OSError as exc:
            if exc.winerror != 5:  # ERROR_ACCESS_DENIED: breakaway refused
                raise
            return _popen(flags)


def _pid_file_stamp() -> tuple[int, int] | None:
    """Return the PID file's (mtime_ns, size), or ``None`` when absent."""
    try:
        st = _PID_PATH.stat()
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size


def _ready_pid(child_pid: int, before: tuple[int, int] | None) -> int | None:
    """Return the daemon's PID once *our* child has written a fresh PID file.

    The daemon writes the file only after its tray and hotkeys are up.  The
    writer is the spawned process itself (frozen build) or, behind a
    venv/uv launcher, that launcher's child.
    """
    if _pid_file_stamp() == before:
        return None
    pid = _read_pid()
    if pid is None:
        return None
    if pid == child_pid:
        return pid
    import psutil

    try:
        return pid if psutil.Process(pid).ppid() == child_pid else None
    except psutil.Error:
        return None


def _stderr_tail() -> str:
    try:
        text = _STDERR_LOG_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-_STDERR_TAIL_LINES:])


def start_daemon() -> int:
    """Start the daemon in the background (idempotent, like ``systemctl start``).

    Returns once the daemon's tray icon and hotkeys are up.

    Returns:
        0 when the daemon started or was already running; 1 when it could not
        be started or did not become ready within :data:`_START_TIMEOUT`.
    """
    if sys.platform != "win32":
        print("press daemon: error: only supported on Windows", file=sys.stderr)
        return 1
    if _probe_running(_read_pid()):
        print(f"press daemon: already running (pid={_read_pid() or '?'})")
        return 0
    if missing := _missing_daemon_modules():
        print(
            f"press daemon: error: the daemon extra is not installed (missing: "
            f"{', '.join(missing)}); reinstall with: uv tool install --reinstall '.[daemon]'",
            file=sys.stderr,
        )
        return 1

    before = _pid_file_stamp()  # a stale file the probe could not remove
    try:
        child = _spawn_daemon()
    except OSError as exc:
        print(f"press daemon: error: could not start: {exc}", file=sys.stderr)
        return 1

    import time

    deadline = time.monotonic() + _START_TIMEOUT
    while True:
        if (pid := _ready_pid(child.pid, before)) is not None:
            print(f"press daemon: started (pid={pid})")
            return 0
        if (code := child.poll()) is not None:
            # Two concurrent starts: the child that lost the mutex exits.
            if _probe_running(None):
                print(f"press daemon: already running (pid={_read_pid() or '?'})")
                return 0
            print(
                f"press daemon: error: daemon exited during start-up (exit code {code})",
                file=sys.stderr,
            )
            if tail := _stderr_tail():
                print(tail, file=sys.stderr)
            print(f"press daemon: see {_STDERR_LOG_PATH} and 'press daemon logs'", file=sys.stderr)
            return 1
        if time.monotonic() >= deadline:
            print(
                f"press daemon: error: still starting after {_START_TIMEOUT:g} s; "
                "check 'press daemon status' and 'press daemon logs'",
                file=sys.stderr,
            )
            return 1
        time.sleep(_START_POLL)


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
    pid = _read_pid()
    running = _probe_running(pid)

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

    # Liveness comes from the probe above, never from status.json: run_daemon
    # writes "state": "running" at startup and nothing rewrites it when the
    # daemon dies, so its state and the PID file describe the *last* run.
    # started_at/version/restart_count still come from it — as last-run facts.
    result: dict[str, object] = {
        "running": running,
        "state": "running" if running else "stopped",
        "pid": pid if running else None,
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
