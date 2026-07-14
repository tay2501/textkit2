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

    from press._pipe import (
        GENERIC_READ,
        GENERIC_WRITE,
        OPEN_EXISTING,
        PIPE_READMODE_MESSAGE,
        SECURITY_SQOS_PRESENT,
        _load_kernel32,
        _read_message,
    )

    # Shared loader: one set of prototypes for the client and server ends.
    _kernel32 = _load_kernel32()

    PIPE_ACCESS_DUPLEX = 0x00000003
    PIPE_TYPE_MESSAGE = 0x00000004
    PIPE_WAIT = 0x00000000
    PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
    PIPE_UNLIMITED_INSTANCES = 255
    # Fail pipe creation instead of silently becoming a second server when
    # another process already owns the name (pipe-squatting detection).
    FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    ERROR_PIPE_CONNECTED = 535
    ERROR_ACCESS_DENIED = 5

    # Owner-only DACL.  The default named-pipe security descriptor grants
    # read access to Everyone and the anonymous account; OWNER_RIGHTS (OW)
    # restricts every access — including connecting and creating further
    # instances — to the account that started the daemon.
    _SDDL_OWNER_ONLY = "D:P(A;;GA;;;OW)"
    _SDDL_REVISION_1 = 1

    class _SecurityAttributes(ctypes.Structure):
        _fields_ = (
            ("nLength", ctypes.c_ulong),
            ("lpSecurityDescriptor", ctypes.c_void_p),
            ("bInheritHandle", ctypes.wintypes.BOOL),
        )

    def _owner_only_security() -> _SecurityAttributes | None:
        """Build SECURITY_ATTRIBUTES restricting the pipe to the owner.

        Returns ``None`` when the SDDL conversion fails; the caller falls
        back to the default DACL rather than losing delegation entirely.
        The descriptor memory stays alive as long as the returned structure
        is referenced (it is LocalAlloc'd and never freed — daemon lifetime).
        """
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        convert = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
        ]
        convert.restype = ctypes.wintypes.BOOL

        descriptor = ctypes.c_void_p(None)
        if not convert(_SDDL_OWNER_ONLY, _SDDL_REVISION_1, ctypes.byref(descriptor), None):
            return None
        return _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), descriptor.value, False)

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
                pipe_name(),
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                SECURITY_SQOS_PRESENT,
                None,
            )
            if handle not in (INVALID_HANDLE_VALUE, None, 0):
                _kernel32.CloseHandle(handle)

        def _accept_loop(self) -> None:
            security = _owner_only_security()
            if security is None:
                _log.warning("pipe: owner-only DACL unavailable; using the default DACL")
            first = True
            while not self._stopping.is_set():
                open_mode = PIPE_ACCESS_DUPLEX
                if first:
                    open_mode |= FILE_FLAG_FIRST_PIPE_INSTANCE
                handle = _kernel32.CreateNamedPipeW(
                    pipe_name(),
                    open_mode,
                    PIPE_TYPE_MESSAGE
                    | PIPE_READMODE_MESSAGE
                    | PIPE_WAIT
                    | PIPE_REJECT_REMOTE_CLIENTS,
                    PIPE_UNLIMITED_INSTANCES,
                    _BUF_SIZE,
                    _BUF_SIZE,
                    0,
                    ctypes.byref(security) if security is not None else None,
                )
                if handle in (INVALID_HANDLE_VALUE, None, 0):
                    err = ctypes.get_last_error()
                    if first and err == ERROR_ACCESS_DENIED:
                        _log.error(
                            "pipe: %s is already owned by another process "
                            "(possible pipe squatting); delegation disabled",
                            pipe_name(),
                        )
                    else:
                        _log.warning("pipe: CreateNamedPipeW failed (%d)", err)
                    return
                first = False

                connected = bool(_kernel32.ConnectNamedPipe(handle, None)) or (
                    ctypes.get_last_error() == ERROR_PIPE_CONNECTED
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
                raw = _read_message(_kernel32, handle)
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

    class PipeServer:
        """No-op stand-in; ``run_daemon`` exits before reaching it off Windows."""

        def __init__(self, dispatcher: CommandDispatcher) -> None:
            self._dispatcher = dispatcher

        def start(self) -> None:
            raise OSError("named pipes are only supported on Windows")

        def stop(self) -> None:
            return
