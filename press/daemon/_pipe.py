"""Named-pipe server: run transforms on behalf of delegating CLI processes.

See :mod:`press._pipe` for the rationale and the wire protocol.  The server
only ever transforms text — it never touches the clipboard or the hold state.
"""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING

from press._pipe import PROTOCOL_VERSION, encode_response, pipe_name
from press.daemon._logs import _log

if TYPE_CHECKING:
    from press.daemon._dispatch import CommandDispatcher

_BUF_SIZE = 64 * 1024


def handle_request(dispatcher: CommandDispatcher, raw: bytes) -> bytes:
    """Decode *raw*, run the transform, and return the encoded reply.

    Free of Win32 calls so it can be tested directly on any platform.
    """
    import json

    from press.commands import (
        PARAMETRIC_ALIASES,
        PARAMETRIC_COMMAND_INDEX,
        SIMPLE_COMMAND_INDEX,
    )

    try:
        request = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return encode_response(ok=False, error=f"malformed request: {exc}")

    if request.get("v") != PROTOCOL_VERSION:
        return encode_response(
            ok=False, error=f"unsupported protocol version: {request.get('v')!r}"
        )

    command = str(request.get("cmd", ""))
    text = request.get("text", "")
    kwargs = request.get("kwargs") or {}
    if not isinstance(text, str) or not isinstance(kwargs, dict):
        return encode_response(ok=False, error="malformed request: bad text or kwargs")

    # Only registry transforms are reachable over the pipe.  Clipboard, hold,
    # and dict commands stay with the caller.
    resolved = PARAMETRIC_ALIASES.get(command, command)
    if resolved in SIMPLE_COMMAND_INDEX:
        allowed: frozenset[str] = frozenset()
    elif resolved in PARAMETRIC_COMMAND_INDEX:
        allowed = frozenset(arg.kwarg for arg in PARAMETRIC_COMMAND_INDEX[resolved].cli_args)
    else:
        return encode_response(ok=False, error=f"unknown command: {command!r}")

    unexpected = set(kwargs) - allowed
    if unexpected:
        return encode_response(ok=False, error=f"unexpected options: {sorted(unexpected)}")

    try:
        result = dispatcher.transform(command, text, kwargs=kwargs)
    except Exception as exc:
        return encode_response(ok=False, error=str(exc))
    return encode_response(ok=True, text=result)


if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    _kernel32 = ctypes.windll.kernel32

    PIPE_ACCESS_DUPLEX = 0x00000003
    PIPE_TYPE_MESSAGE = 0x00000004
    PIPE_READMODE_MESSAGE = 0x00000002
    PIPE_WAIT = 0x00000000
    PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
    PIPE_UNLIMITED_INSTANCES = 255
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    ERROR_PIPE_CONNECTED = 535
    ERROR_MORE_DATA = 234
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3

    # Explicit types so HANDLEs survive on 64-bit (see clipboard.py).
    _kernel32.CreateNamedPipeW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
    ]
    _kernel32.CreateNamedPipeW.restype = ctypes.c_void_p
    _kernel32.ConnectNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _kernel32.ConnectNamedPipe.restype = ctypes.wintypes.BOOL
    _kernel32.DisconnectNamedPipe.argtypes = [ctypes.c_void_p]
    _kernel32.DisconnectNamedPipe.restype = ctypes.wintypes.BOOL
    _kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
    ]
    _kernel32.CreateFileW.restype = ctypes.c_void_p
    _kernel32.ReadFile.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_void_p,
    ]
    _kernel32.ReadFile.restype = ctypes.wintypes.BOOL
    _kernel32.WriteFile.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_void_p,
    ]
    _kernel32.WriteFile.restype = ctypes.wintypes.BOOL
    _kernel32.FlushFileBuffers.argtypes = [ctypes.c_void_p]
    _kernel32.FlushFileBuffers.restype = ctypes.wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    _kernel32.CloseHandle.restype = ctypes.wintypes.BOOL

    def _read_message(handle: int) -> bytes | None:
        """Read one pipe message, following ERROR_MORE_DATA continuations."""
        chunks: list[bytes] = []
        buf = ctypes.create_string_buffer(_BUF_SIZE)
        read = ctypes.c_ulong(0)
        while True:
            ok = _kernel32.ReadFile(handle, buf, _BUF_SIZE, ctypes.byref(read), None)
            chunks.append(buf.raw[: read.value])
            if ok:
                return b"".join(chunks)
            if _kernel32.GetLastError() != ERROR_MORE_DATA:
                return None

    class PipeServer:
        """Accept transform requests from CLI processes on a named pipe.

        Args:
            dispatcher: Runs the transforms; already warm in the daemon process.
        """

        def __init__(self, dispatcher: CommandDispatcher) -> None:
            self._dispatcher = dispatcher
            self._stopping = threading.Event()
            self._thread: threading.Thread | None = None

        def start(self) -> None:
            """Begin accepting connections on a background daemon thread."""
            self._thread = threading.Thread(
                target=self._accept_loop, name="press-pipe", daemon=True
            )
            self._thread.start()

        def stop(self) -> None:
            """Stop accepting connections, unblocking a pending ConnectNamedPipe."""
            self._stopping.set()
            self._poke()

        def _poke(self) -> None:
            """Connect to our own pipe so the blocked accept call returns."""
            handle = _kernel32.CreateFileW(
                pipe_name(), GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None
            )
            if handle not in (INVALID_HANDLE_VALUE, None, 0):
                _kernel32.CloseHandle(handle)

        def _accept_loop(self) -> None:
            while not self._stopping.is_set():
                handle = _kernel32.CreateNamedPipeW(
                    pipe_name(),
                    PIPE_ACCESS_DUPLEX,
                    PIPE_TYPE_MESSAGE
                    | PIPE_READMODE_MESSAGE
                    | PIPE_WAIT
                    | PIPE_REJECT_REMOTE_CLIENTS,
                    PIPE_UNLIMITED_INSTANCES,
                    _BUF_SIZE,
                    _BUF_SIZE,
                    0,
                    None,  # default DACL: this user and administrators only
                )
                if handle in (INVALID_HANDLE_VALUE, None, 0):
                    _log.warning("pipe: CreateNamedPipeW failed (%d)", _kernel32.GetLastError())
                    return

                connected = bool(_kernel32.ConnectNamedPipe(handle, None)) or (
                    _kernel32.GetLastError() == ERROR_PIPE_CONNECTED
                )
                if self._stopping.is_set():
                    _kernel32.CloseHandle(handle)
                    return
                if not connected:
                    _kernel32.CloseHandle(handle)
                    continue

                worker = threading.Thread(target=self._serve, args=(handle,), daemon=True)
                worker.start()

        def _serve(self, handle: int) -> None:
            try:
                raw = _read_message(handle)
                if raw:
                    reply = handle_request(self._dispatcher, raw)
                    written = ctypes.c_ulong(0)
                    _kernel32.WriteFile(handle, reply, len(reply), ctypes.byref(written), None)
                    _kernel32.FlushFileBuffers(handle)
            except Exception as exc:  # a bad client must never kill the daemon
                _log.warning("pipe: request failed: %s", exc)
            finally:
                _kernel32.DisconnectNamedPipe(handle)
                _kernel32.CloseHandle(handle)

else:  # pragma: no cover — the daemon only runs on Windows

    class PipeServer:  # type: ignore[no-redef]
        """No-op stand-in; ``run_daemon`` exits before reaching it off Windows."""

        def __init__(self, dispatcher: CommandDispatcher) -> None:
            self._dispatcher = dispatcher

        def start(self) -> None:
            raise OSError("named pipes are only supported on Windows")

        def stop(self) -> None:
            return
