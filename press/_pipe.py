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


def pipe_name() -> str:
    """Return the per-user named-pipe path.

    Named pipes share one machine-wide namespace, so the account name keeps
    two users' daemons from colliding on a shared machine.
    """
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "default"
    return rf"\\.\pipe\press-daemon-v{PROTOCOL_VERSION}-{user}"


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
    """
    import threading

    result: list[bytes | None] = [None]

    def _call() -> None:
        result[0] = _round_trip(request)

    worker = threading.Thread(target=_call, daemon=True)
    worker.start()
    worker.join(_CLIENT_TIMEOUT)
    return result[0]


# ---------------------------------------------------------------------------
# Win32 pipe client — ctypes is imported on first use, never at module import
# ---------------------------------------------------------------------------

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
PIPE_READMODE_MESSAGE = 0x00000002
ERROR_MORE_DATA = 234

_kernel32: Any = None


def _load_kernel32() -> Any:
    """Import ctypes and declare the pipe prototypes once."""
    global _kernel32
    if _kernel32 is not None:
        return _kernel32

    import ctypes
    import ctypes.wintypes

    k32 = ctypes.windll.kernel32
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

    _kernel32 = k32
    return k32


def _round_trip(request: bytes) -> bytes | None:
    """Send *request* to the daemon pipe and return the raw reply."""
    if sys.platform != "win32":  # pragma: no cover — delegation is Windows-only
        return None

    import ctypes

    k32 = _load_kernel32()
    invalid = ctypes.c_void_p(-1).value

    handle = k32.CreateFileW(
        pipe_name(), GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None
    )
    if handle in (invalid, None, 0):
        return None  # no daemon listening

    try:
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
    import ctypes

    chunks: list[bytes] = []
    buf = ctypes.create_string_buffer(_BUF_SIZE)
    read = ctypes.c_ulong(0)
    while True:
        ok = k32.ReadFile(handle, buf, _BUF_SIZE, ctypes.byref(read), None)
        chunks.append(buf.raw[: read.value])
        if ok:
            return b"".join(chunks)
        if k32.GetLastError() != ERROR_MORE_DATA:
            return None
