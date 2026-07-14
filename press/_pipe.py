"""Named-pipe protocol and CLI client for delegating transforms to the daemon.

Why this exists
---------------
On EDR/DLP-monitored machines the dominant cost of ``press <cmd>`` is not the
transform (≤2ms) but the file opens the interpreter performs while importing
the transform module and its dependencies.  Each open is inspected by the
security agent, so the cost scales with how heavy the command's imports are:
``fix-encoding`` (charset_normalizer) opened 154 files versus 54 for the bare
CLI.

A running daemon already holds those modules in memory.  The CLI hands it the
work over a named pipe and skips the import, which flattens every command to
the same bounded cost.  With no daemon the CLI transforms in-process exactly
as before.  Nothing here changes observable behaviour — only who does the work.

Import budget
-------------
This module is imported on every transform, so its body pulls in nothing
beyond ``json``/``os``/``sys``.  ``ctypes`` and ``threading`` cost 8 file
opens between them and are imported only after :func:`_daemon_may_be_running`
says a daemon is plausibly listening — otherwise delegation would make the
no-daemon path *slower* on exactly the machines this exists to help.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

PROTOCOL_VERSION = 1

# Response deadline.  Transforms finish in single-digit milliseconds; a wedged
# daemon must never hang the CLI, so we give up and transform locally instead.
_CLIENT_TIMEOUT = 2.0

_BUF_SIZE = 64 * 1024


def user_name() -> str:
    """Return the account name that scopes per-user daemon resources.

    Shared by :func:`pipe_name` and the daemon singleton mutex
    (:mod:`press.daemon._lifecycle`) so both resolve to the same scope;
    ``test_pipe.py`` asserts they agree.
    """
    return os.environ.get("USERNAME") or os.environ.get("USER") or "default"


def pipe_name() -> str:
    """Return the per-user named-pipe path.

    Named pipes share one machine-wide namespace, so the account name keeps
    two users' daemons from colliding on a shared machine.
    """
    return rf"\\.\pipe\press-daemon-v{PROTOCOL_VERSION}-{user_name()}"


def daemon_pid_path() -> str:
    """Return the daemon PID file path, derived without importing ``pathlib``.

    Mirrors ``press._paths.press_dir() / "press.pid"``.  The duplication is
    deliberate: importing ``pathlib`` here would cost 20 file opens on every
    transform, defeating the purpose of this module.  ``test_pipe.py`` asserts
    the two derivations agree.
    """
    base = os.environ.get("APPDATA") or os.path.expanduser("~")  # noqa: PTH111
    return os.path.join(base, "press", "press.pid")  # noqa: PTH118


def _daemon_may_be_running() -> bool:
    """Cheap liveness gate: does the daemon's PID file exist?

    A stat is far cheaper than the ctypes import a real pipe probe needs.  A
    stale PID file merely costs one failed connect before the local fallback.
    """
    return os.path.exists(daemon_pid_path())  # noqa: PTH110


def encode_request(command: str, text: str, kwargs: dict[str, object]) -> bytes:
    """Serialize a transform request."""
    return json.dumps(
        {"v": PROTOCOL_VERSION, "cmd": command, "text": text, "kwargs": kwargs},
        ensure_ascii=False,
    ).encode("utf-8")


def encode_response(*, ok: bool, text: str = "", error: str = "") -> bytes:
    """Serialize a transform response."""
    payload = {"ok": ok, "text": text} if ok else {"ok": False, "error": error}
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class DaemonTransformError(Exception):
    """The daemon ran the transform and it failed.

    Raised so the CLI reports the daemon's message through its normal error
    path, rather than silently re-running the same failing transform locally.
    """


def try_delegate(command: str, text: str, kwargs: dict[str, object]) -> str | None:
    """Ask a running daemon to transform *text*, or return ``None``.

    ``None`` means "no daemon available" for any reason — not running, not
    Windows, pipe error, malformed reply — and the caller must transform
    in-process.

    Raises:
        DaemonTransformError: The daemon executed the transform and it failed.
    """
    if sys.platform != "win32":
        return None
    if os.environ.get("PRESS_NO_DAEMON"):
        return None
    if not _daemon_may_be_running():
        return None

    try:
        request = encode_request(command, text, kwargs)
    except UnicodeEncodeError:
        # Lone surrogates survive a local transform but cannot cross the wire.
        return None

    raw = _round_trip_with_timeout(request)
    if raw is None:
        return None

    try:
        reply = json.loads(raw.decode("utf-8"))
        if reply.get("ok"):
            return str(reply["text"])
        error = str(reply.get("error", "unknown daemon error"))
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
        return None  # unusable reply — fall back to a local transform

    raise DaemonTransformError(error)


def _round_trip_with_timeout(request: bytes) -> bytes | None:
    """Run the blocking pipe exchange under a deadline.

    The I/O happens on a throwaway daemon thread, so a wedged daemon costs
    ``_CLIENT_TIMEOUT`` seconds and then the local fallback, never a hang.
    On timeout the worker's blocked pipe I/O is cancelled so it releases its
    pipe handle instead of leaking it for the rest of the process lifetime.
    """
    import threading

    result: list[bytes | None] = [None]
    worker_tid: list[int] = []

    def _call() -> None:
        worker_tid.append(threading.get_native_id())
        result[0] = _round_trip(request)

    worker = threading.Thread(target=_call, daemon=True)
    worker.start()
    worker.join(_CLIENT_TIMEOUT)
    if worker.is_alive() and worker_tid:
        _cancel_pending_io(worker_tid[0])
        worker.join(0.2)
    return result[0]


def _cancel_pending_io(thread_id: int) -> None:
    """Cancel blocked synchronous pipe I/O on the worker thread (best effort).

    ``CancelSynchronousIo`` makes the worker's ReadFile/WriteFile return
    ERROR_OPERATION_ABORTED, so its ``finally`` block closes the pipe handle.
    Only called on the timeout path, where ctypes is already imported.
    """
    k32 = _load_kernel32()
    thread_terminate = 0x0001  # access right CancelSynchronousIo requires
    handle = k32.OpenThread(thread_terminate, False, thread_id)
    if handle:
        k32.CancelSynchronousIo(handle)
        k32.CloseHandle(handle)


# ---------------------------------------------------------------------------
# Win32 pipe client — ctypes is imported on first use, never at module import
# ---------------------------------------------------------------------------

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
PIPE_READMODE_MESSAGE = 0x00000002
ERROR_MORE_DATA = 234
# SECURITY_SQOS_PRESENT with SECURITY_ANONYMOUS (impersonation level 0): a
# rogue process squatting on the pipe name must not be able to impersonate
# this client's token via ImpersonateNamedPipeClient.
SECURITY_SQOS_PRESENT = 0x00100000

_kernel32: Any = None


def _load_kernel32() -> Any:
    """Import ctypes and declare the pipe prototypes once.

    Declares both the client-side and server-side pipe functions so
    :mod:`press.daemon._pipe` can share this loader — the extra ``argtypes``
    assignments cost no file opens, which is all this module's budget cares
    about.  ``use_last_error=True`` because calling ``GetLastError()``
    through ctypes is unreliable (ctypes itself may overwrite it); the
    official ctypes docs prescribe :func:`ctypes.get_last_error` instead.
    """
    if sys.platform != "win32":  # pragma: no cover — Win32 APIs only
        raise OSError("the Win32 loader requires Windows")

    global _kernel32
    if _kernel32 is not None:
        return _kernel32

    import ctypes
    import ctypes.wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    # Explicit types so HANDLEs survive on 64-bit (see clipboard.py).
    k32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
    ]
    k32.CreateFileW.restype = ctypes.c_void_p
    k32.SetNamedPipeHandleState.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    k32.SetNamedPipeHandleState.restype = ctypes.wintypes.BOOL
    k32.GetNamedPipeServerProcessId.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    k32.GetNamedPipeServerProcessId.restype = ctypes.wintypes.BOOL
    k32.WriteFile.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_void_p,
    ]
    k32.WriteFile.restype = ctypes.wintypes.BOOL
    k32.ReadFile.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_void_p,
    ]
    k32.ReadFile.restype = ctypes.wintypes.BOOL
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.CloseHandle.restype = ctypes.wintypes.BOOL
    # Timeout path: cancel a worker thread's blocked synchronous pipe I/O.
    k32.OpenThread.argtypes = [ctypes.c_ulong, ctypes.wintypes.BOOL, ctypes.c_ulong]
    k32.OpenThread.restype = ctypes.c_void_p
    k32.CancelSynchronousIo.argtypes = [ctypes.c_void_p]
    k32.CancelSynchronousIo.restype = ctypes.wintypes.BOOL
    # Daemon singleton mutex (press.daemon._lifecycle) — shared loader keeps
    # kernel32 prototypes in one place (see CLAUDE.md).
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.c_wchar_p]
    k32.CreateMutexW.restype = ctypes.c_void_p
    # Server side (press.daemon._pipe) — free to declare here, unused by the CLI.
    k32.CreateNamedPipeW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
    ]
    k32.CreateNamedPipeW.restype = ctypes.c_void_p
    k32.ConnectNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.ConnectNamedPipe.restype = ctypes.wintypes.BOOL
    k32.DisconnectNamedPipe.argtypes = [ctypes.c_void_p]
    k32.DisconnectNamedPipe.restype = ctypes.wintypes.BOOL
    k32.FlushFileBuffers.argtypes = [ctypes.c_void_p]
    k32.FlushFileBuffers.restype = ctypes.wintypes.BOOL

    _kernel32 = k32
    return k32


def _daemon_pid_from_file() -> int | None:
    """Return the PID recorded by the running daemon, or ``None``."""
    try:
        with open(daemon_pid_path(), encoding="utf-8") as fh:  # noqa: PTH123
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def _server_is_our_daemon(k32: Any, handle: int) -> bool:
    """Verify the pipe server is the process our PID file points at.

    Named-pipe names are first-come-first-served, so a malicious local
    process could claim the name while no daemon instance holds it and
    harvest the text the CLI sends.  Comparing the server's PID against the
    daemon's PID file closes that window; on mismatch the caller falls back
    to the local transform.  The PID file read costs one extra file open on
    the delegation path only — the no-daemon path still pays a single stat.
    """
    import ctypes

    expected = _daemon_pid_from_file()
    if expected is None:
        return False
    server = ctypes.c_ulong(0)
    if not k32.GetNamedPipeServerProcessId(handle, ctypes.byref(server)):
        return False
    return server.value == expected


def _round_trip(request: bytes) -> bytes | None:
    """Send *request* to the daemon pipe and return the raw reply."""
    if sys.platform != "win32":  # pragma: no cover — delegation is Windows-only
        return None

    import ctypes

    k32 = _load_kernel32()
    invalid = ctypes.c_void_p(-1).value

    handle = k32.CreateFileW(
        pipe_name(),
        GENERIC_READ | GENERIC_WRITE,
        0,
        None,
        OPEN_EXISTING,
        SECURITY_SQOS_PRESENT,  # anonymous impersonation level
        None,
    )
    if handle in (invalid, None, 0):
        return None  # no daemon listening

    try:
        if not _server_is_our_daemon(k32, handle):
            return None  # not our daemon — never send it the text

        mode = ctypes.c_ulong(PIPE_READMODE_MESSAGE)
        if not k32.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None):
            return None

        written = ctypes.c_ulong(0)
        if not k32.WriteFile(handle, request, len(request), ctypes.byref(written), None):
            return None

        return _read_message(k32, handle)
    finally:
        k32.CloseHandle(handle)


def _read_message(k32: Any, handle: int) -> bytes | None:
    """Read one pipe message, following ERROR_MORE_DATA continuations."""
    if sys.platform != "win32":  # pragma: no cover — Win32 APIs only
        raise OSError("named pipes require Windows")

    import ctypes

    chunks: list[bytes] = []
    buf = ctypes.create_string_buffer(_BUF_SIZE)
    read = ctypes.c_ulong(0)
    while True:
        ok = k32.ReadFile(handle, buf, _BUF_SIZE, ctypes.byref(read), None)
        chunks.append(buf.raw[: read.value])
        if ok:
            return b"".join(chunks)
        if ctypes.get_last_error() != ERROR_MORE_DATA:
            return None
