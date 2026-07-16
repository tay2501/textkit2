"""Clipboard read/write via ctypes (Windows) with cross-platform fallback."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def get_clipboard_text() -> str:
    """Read text from the system clipboard.

    Returns:
        Text content of the clipboard.

    Raises:
        RuntimeError: If clipboard access fails or clipboard is empty.
        OSError: On non-Windows platforms where clipboard access is unavailable.
    """
    if sys.platform == "win32":
        return _win_get_text()
    raise OSError("Clipboard access is only supported on Windows")


def set_clipboard_text(text: str, *, sensitive: bool = False) -> None:
    """Write text to the system clipboard.

    Args:
        text: Text to place on the clipboard.
        sensitive: When ``True``, mark the content as excluded from the
            Win+V clipboard history and Cloud Clipboard sync (the formats
            password managers use).  If the marking fails the clipboard is
            wiped and the error raised — a secret must never sit on the
            clipboard unmarked.

    Raises:
        RuntimeError: If clipboard access fails.
        OSError: On non-Windows platforms where clipboard access is unavailable.
    """
    if sys.platform == "win32":
        _win_set_text(text, sensitive=sensitive)
        return
    raise OSError("Clipboard access is only supported on Windows")


def clear_clipboard() -> None:
    """Clear the system clipboard (remove all contents).

    Raises:
        RuntimeError: If clipboard access fails.
        OSError: On non-Windows platforms where clipboard access is unavailable.
    """
    if sys.platform == "win32":
        _win_clear()
        return
    raise OSError("Clipboard access is only supported on Windows")


def get_clipboard_sequence_number() -> int:
    """Return the current clipboard sequence number.

    Windows increments the number on every clipboard change, so a caller
    that wrote a secret can later detect whether the clipboard still holds
    that value (e.g. before auto-clearing a password).

    Returns:
        The clipboard sequence number for the current window station.

    Raises:
        OSError: On non-Windows platforms where clipboard access is unavailable.
    """
    if sys.platform == "win32":
        return _win_sequence_number()
    raise OSError("Clipboard access is only supported on Windows")


def clear_clipboard_if_unchanged(sequence_number: int) -> bool:
    """Clear the clipboard only if it has not changed since *sequence_number*.

    The KeePass/Bitwarden-style conditional auto-clear: a timer that wipes
    a copied secret must not destroy something else the user copied in the
    meantime.  The check and the clear happen while the clipboard is held
    open, so no other process can slip a write between them.

    Args:
        sequence_number: Value captured via :func:`get_clipboard_sequence_number`
            right after writing the secret.

    Returns:
        ``True`` when the clipboard was cleared, ``False`` when another
        application changed it in the meantime (it is left untouched).

    Raises:
        RuntimeError: If clipboard access fails.
        OSError: On non-Windows platforms where clipboard access is unavailable.
    """
    if sys.platform == "win32":
        return _win_clear_if_unchanged(sequence_number)
    raise OSError("Clipboard access is only supported on Windows")


def clipboard_has_sensitive_marks() -> bool:
    """Report whether the current clipboard content carries an exclusion format.

    ``True`` means the writer (press genpass, KeePassXC, Bitwarden, …) marked
    the content with one of the cooperative exclusion formats
    (``_SENSITIVE_FORMATS``).  press honours its own marks: such content is
    never captured into the undo snapshot.

    Uses ``IsClipboardFormatAvailable`` which needs no ``OpenClipboard``.

    Raises:
        OSError: On non-Windows platforms where clipboard access is unavailable.
    """
    if sys.platform == "win32":
        return _win_has_sensitive_marks()
    raise OSError("Clipboard access is only supported on Windows")


# ---------------------------------------------------------------------------
# Windows implementation via ctypes
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    # use_last_error=True: reading GetLastError() through ctypes is unreliable
    # (ctypes itself may overwrite it); the official ctypes docs prescribe
    # ctypes.get_last_error() instead — same rule as _pipe.py / _lifecycle.py.
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    # 64ビット環境でポインタ/HANDLEが正しく扱われるよう型を明示する
    _user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    _user32.OpenClipboard.restype = ctypes.wintypes.BOOL
    _user32.CloseClipboard.argtypes = []
    _user32.CloseClipboard.restype = ctypes.wintypes.BOOL
    _user32.EmptyClipboard.argtypes = []
    _user32.EmptyClipboard.restype = ctypes.wintypes.BOOL
    _user32.GetClipboardData.restype = ctypes.c_void_p
    _user32.GetClipboardData.argtypes = [ctypes.c_uint]
    _user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    _user32.SetClipboardData.restype = ctypes.c_void_p
    _kernel32.GlobalAlloc.restype = ctypes.c_void_p
    _kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    _kernel32.GlobalLock.restype = ctypes.c_void_p
    _kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    _user32.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
    _user32.RegisterClipboardFormatW.restype = ctypes.c_uint
    _user32.GetClipboardSequenceNumber.argtypes = []
    _user32.GetClipboardSequenceNumber.restype = ctypes.wintypes.DWORD
    _user32.IsClipboardFormatAvailable.argtypes = [ctypes.c_uint]
    _user32.IsClipboardFormatAvailable.restype = ctypes.wintypes.BOOL

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    # Formats honoured by Win+V history and Cloud Clipboard (Microsoft Learn,
    # "Clipboard Formats").  The presence of the Exclude… format keeps the
    # content out of both; the DWORD-0 formats are belt-and-suspenders for
    # monitors that only honour the specific ones.  KeePassXC and Chrome
    # Incognito set the same formats for secrets.
    # "Clipboard Viewer Ignore" is the older cooperative convention honoured
    # by classic clipboard managers (Ditto, ClipboardFusion); its mere
    # presence is the signal, the payload is irrelevant.
    _SENSITIVE_FORMATS = (
        "ExcludeClipboardContentFromMonitorProcessing",
        "CanIncludeInClipboardHistory",
        "CanUploadToCloudClipboard",
        "Clipboard Viewer Ignore",
    )

    def _win_get_text() -> str:
        if not _user32.OpenClipboard(None):
            raise RuntimeError("Failed to open clipboard")
        try:
            handle = _user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                raise RuntimeError("Clipboard is empty or does not contain text")
            ptr = _kernel32.GlobalLock(handle)
            if not ptr:
                raise RuntimeError("Failed to lock clipboard memory")
            try:
                return ctypes.wstring_at(ptr)
            finally:
                _kernel32.GlobalUnlock(handle)
        finally:
            _user32.CloseClipboard()

    def _alloc_global(data: bytes) -> int:
        """Copy *data* into a GMEM_MOVEABLE block and return its handle."""
        h_mem = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h_mem:
            raise RuntimeError("Failed to allocate clipboard memory")
        ptr = _kernel32.GlobalLock(h_mem)
        if not ptr:
            _kernel32.GlobalFree(h_mem)
            raise RuntimeError("Failed to lock clipboard memory")
        try:
            ctypes.memmove(ptr, data, len(data))
        finally:
            _kernel32.GlobalUnlock(h_mem)
        return int(h_mem)

    def _set_clipboard_format(fmt: int, data: bytes) -> None:
        """SetClipboardData with ownership-correct cleanup on failure."""
        h_mem = _alloc_global(data)
        if not _user32.SetClipboardData(fmt, h_mem):
            # Ownership only passes to the system on success.
            _kernel32.GlobalFree(h_mem)
            raise RuntimeError(f"Failed to set clipboard data (error {ctypes.get_last_error()})")

    def _mark_clipboard_sensitive() -> None:
        """Exclude the current clipboard content from Win+V history and sync."""
        for name in _SENSITIVE_FORMATS:
            fmt = _user32.RegisterClipboardFormatW(name)
            if not fmt:
                raise RuntimeError(
                    f"Failed to register clipboard format {name!r} "
                    f"(error {ctypes.get_last_error()})"
                )
            _set_clipboard_format(fmt, (0).to_bytes(4, "little"))  # DWORD 0 = opt out

    def _win_set_text(text: str, *, sensitive: bool = False) -> None:
        encoded = (text + "\x00").encode("utf-16-le")

        if not _user32.OpenClipboard(None):
            raise RuntimeError("Failed to open clipboard")
        try:
            # Both calls can genuinely fail (RDP sessions, clipboard managers,
            # Office holding the clipboard).  A failure must raise instead of
            # silently leaving the old clipboard content in place.
            if not _user32.EmptyClipboard():
                raise RuntimeError(f"Failed to empty clipboard (error {ctypes.get_last_error()})")
            _set_clipboard_format(CF_UNICODETEXT, encoded)
            if sensitive:
                try:
                    _mark_clipboard_sensitive()
                except RuntimeError:
                    # Never leave a secret on the clipboard without the
                    # exclusion marks — wipe it, then report the failure.
                    _user32.EmptyClipboard()
                    raise
        finally:
            _user32.CloseClipboard()

    def _win_clear() -> None:
        if not _user32.OpenClipboard(None):
            raise RuntimeError("Failed to open clipboard")
        try:
            if not _user32.EmptyClipboard():
                raise RuntimeError(f"Failed to empty clipboard (error {ctypes.get_last_error()})")
        finally:
            _user32.CloseClipboard()

    def _win_sequence_number() -> int:
        return int(_user32.GetClipboardSequenceNumber())

    def _win_clear_if_unchanged(sequence_number: int) -> bool:
        if not _user32.OpenClipboard(None):
            raise RuntimeError("Failed to open clipboard")
        try:
            # While we hold the clipboard open no other process can write to
            # it, so the sequence check and the clear are effectively atomic.
            if int(_user32.GetClipboardSequenceNumber()) != sequence_number:
                return False
            if not _user32.EmptyClipboard():
                raise RuntimeError(f"Failed to empty clipboard (error {ctypes.get_last_error()})")
            return True
        finally:
            _user32.CloseClipboard()

    def _win_has_sensitive_marks() -> bool:
        # A failed RegisterClipboardFormatW (fmt == 0) cannot be probed;
        # treat it as unmarked rather than failing the caller, which only
        # uses this as a "do not snapshot" guard.
        return any(
            (fmt := _user32.RegisterClipboardFormatW(name))
            and _user32.IsClipboardFormatAvailable(fmt)
            for name in _SENSITIVE_FORMATS
        )

    # -----------------------------------------------------------------------
    # Win32 constants for clipboard monitoring
    # -----------------------------------------------------------------------

    WM_CLIPBOARDUPDATE = 0x031D
    WM_CLOSE = 0x0010
    WM_DESTROY = 0x0002

    # WNDPROC function type: LRESULT CALLBACK(HWND, UINT, WPARAM, LPARAM)
    # LRESULT is LONG_PTR — pointer-sized and signed (64-bit on x64); c_long
    # would truncate the upper 32 bits of pointer-valued results.
    _WNDPROC = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_size_t,
    )

    # WNDCLASSEXW structure (manual definition — not in ctypes.wintypes)
    class _WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("style", ctypes.c_uint),
            ("lpfnWndProc", _WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", ctypes.c_void_p),
            ("hIcon", ctypes.c_void_p),
            ("hCursor", ctypes.c_void_p),
            ("hbrBackground", ctypes.c_void_p),
            ("lpszMenuName", ctypes.c_wchar_p),
            ("lpszClassName", ctypes.c_wchar_p),
            ("hIconSm", ctypes.c_void_p),
        ]

    # Additional Win32 API declarations for the monitor window
    _user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
    _user32.RegisterClassExW.restype = ctypes.c_ushort
    _user32.CreateWindowExW.argtypes = [
        ctypes.c_ulong,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    _user32.CreateWindowExW.restype = ctypes.c_void_p
    _user32.DestroyWindow.argtypes = [ctypes.c_void_p]
    _user32.DestroyWindow.restype = ctypes.wintypes.BOOL
    _user32.AddClipboardFormatListener.argtypes = [ctypes.c_void_p]
    _user32.AddClipboardFormatListener.restype = ctypes.wintypes.BOOL
    _user32.RemoveClipboardFormatListener.argtypes = [ctypes.c_void_p]
    _user32.RemoveClipboardFormatListener.restype = ctypes.wintypes.BOOL
    _user32.PostMessageW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_size_t,
    ]
    _user32.PostMessageW.restype = ctypes.wintypes.BOOL
    _user32.PostQuitMessage.argtypes = [ctypes.c_int]
    _user32.PostQuitMessage.restype = None
    _user32.DefWindowProcW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_size_t,
    ]
    _user32.DefWindowProcW.restype = ctypes.c_ssize_t  # LRESULT (LONG_PTR)
    _user32.GetMessageW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_uint,
    ]
    _user32.GetMessageW.restype = ctypes.wintypes.BOOL
    _user32.TranslateMessage.argtypes = [ctypes.c_void_p]
    _user32.TranslateMessage.restype = ctypes.wintypes.BOOL
    _user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
    _user32.DispatchMessageW.restype = ctypes.c_ssize_t  # LRESULT (LONG_PTR)
    _kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    _kernel32.GetModuleHandleW.restype = ctypes.c_void_p

    # -----------------------------------------------------------------------
    # _ClipboardMonitorWindow
    # -----------------------------------------------------------------------

    # Layer-1 conflict detection: if another resident tool (clipboard history
    # manager, sync agent) also rewrites the clipboard, mutual restores
    # ping-pong indefinitely.  More than _STORM_LIMIT restores within
    # _STORM_WINDOW seconds triggers on_storm so the guard can auto-release
    # instead of fighting forever.
    _STORM_LIMIT = 15
    _STORM_WINDOW = 3.0

    class _ClipboardMonitorWindow:
        """Layer 1: Hidden Win32 window that listens for WM_CLIPBOARDUPDATE.

        When the clipboard changes (and a restore is not already in progress),
        the protected text is immediately written back to the clipboard.

        Args:
            get_text: Callable that returns the current protected text, or
                ``None`` if the guard is not active.
            on_storm: Called (from the monitor thread) when restores exceed
                the storm threshold — another app is fighting for the
                clipboard and the guard should stand down.
        """

        def __init__(
            self,
            get_text: Callable[[], str | None],
            on_storm: Callable[[], None] | None = None,
        ) -> None:
            self._get_text = get_text
            self._on_storm = on_storm
            self._restoring: bool = False
            self._hwnd: int | None = None
            self._restore_times: list[float] = []

        def _on_clipboard_update(self) -> None:
            """Called when WM_CLIPBOARDUPDATE is received.

            Guards against re-entrant calls that would cause an infinite loop
            (our own SetClipboardData triggers WM_CLIPBOARDUPDATE again).
            """
            if self._restoring:
                return
            text = self._get_text()
            if text is None:
                return
            if self._storm_detected():
                # Let the other application win — restoring once more would
                # just prolong the war.
                if self._on_storm is not None:
                    self._on_storm()
                return
            self._restoring = True
            try:
                _win_set_text(text)
            finally:
                self._restoring = False

        def _storm_detected(self) -> bool:
            """Record a restore attempt; True when the rate exceeds the limit."""
            import time

            now = time.monotonic()
            self._restore_times = [t for t in self._restore_times if now - t <= _STORM_WINDOW]
            self._restore_times.append(now)
            return len(self._restore_times) >= _STORM_LIMIT

        def start(self) -> None:  # pragma: no cover
            """Create the hidden window and start the message loop in a thread."""
            import threading

            ready = threading.Event()
            self._restore_times = []  # re-arm resets the storm window

            # Keep a strong reference to the WNDPROC so it is not GC'd
            self._wnd_proc_ref = _WNDPROC(self._wnd_proc)

            def _thread_func() -> None:
                wnd_class = _WNDCLASSEXW()
                wnd_class.cbSize = ctypes.sizeof(wnd_class)
                wnd_class.lpfnWndProc = self._wnd_proc_ref
                wnd_class.hInstance = _kernel32.GetModuleHandleW(None)
                wnd_class.lpszClassName = "pressClipboardMonitor"
                _user32.RegisterClassExW(ctypes.byref(wnd_class))

                hwnd = _user32.CreateWindowExW(
                    0,
                    "pressClipboardMonitor",
                    "pressClipboardMonitor",
                    0,
                    0,
                    0,
                    0,
                    0,
                    None,
                    None,
                    _kernel32.GetModuleHandleW(None),
                    None,
                )
                self._hwnd = hwnd
                _user32.AddClipboardFormatListener(hwnd)
                ready.set()

                msg = ctypes.wintypes.MSG()
                # GetMessageW returns -1 on error, 0 on WM_QUIT; `> 0` exits on
                # both instead of busy-looping on a persistent error.
                while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    _user32.TranslateMessage(ctypes.byref(msg))
                    _user32.DispatchMessageW(ctypes.byref(msg))

            t = threading.Thread(target=_thread_func, daemon=True, name="press-cb-monitor")
            t.start()
            ready.wait(timeout=2.0)

        def _wnd_proc(  # pragma: no cover
            self,
            hwnd: int,
            msg: int,
            wparam: int,
            lparam: int,
        ) -> int:
            """Window procedure that handles clipboard update and destroy messages."""
            if msg == WM_CLIPBOARDUPDATE:
                self._on_clipboard_update()
                return 0
            if msg == WM_DESTROY:
                _user32.RemoveClipboardFormatListener(hwnd)
                _user32.PostQuitMessage(0)
                return 0
            return int(_user32.DefWindowProcW(hwnd, msg, wparam, lparam))

        def stop(self) -> None:  # pragma: no cover
            """Send WM_CLOSE to the hidden window to terminate the message loop."""
            if self._hwnd is not None:
                _user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
                self._hwnd = None

    # -----------------------------------------------------------------------
    # _PasteInterceptor
    # -----------------------------------------------------------------------

    class _PasteInterceptor:
        """Layer 2: Detects Ctrl+V / Shift+Insert and pre-loads the clipboard.

        Because the pynput WH_KEYBOARD_LL hook fires *before* the OS dispatches
        the key event, setting the clipboard here ensures the protected text is
        in place before any receiving application can read it.

        Args:
            (none at construction — call start() to arm with a text supplier)
        """

        def __init__(self) -> None:
            self._ctrl_held: bool = False
            self._shift_held: bool = False
            self._listener: Any | None = None
            self._get_text: Callable[[], str | None] | None = None

        def _is_paste_shortcut(self, key: object) -> bool:
            """Return True if *key* is Ctrl+V or Shift+Insert.

            Uses duck typing rather than isinstance so that tests can pass
            lightweight mock objects without requiring pynput to be importable
            in the test runner.
            """
            if self._ctrl_held:
                char = getattr(key, "char", None)
                if char == "v":
                    return True
            if self._shift_held:
                # Compare by name attribute for Key.insert duck typing
                name = getattr(key, "name", None)
                if name == "insert":
                    return True
            return False

        def _on_press(self, key: object) -> None:  # pragma: no cover
            from pynput import keyboard as kb

            # Track modifier state
            if key in (kb.Key.ctrl, kb.Key.ctrl_l, kb.Key.ctrl_r):
                self._ctrl_held = True
            elif key in (kb.Key.shift, kb.Key.shift_l, kb.Key.shift_r):
                self._shift_held = True

            if self._is_paste_shortcut(key) and self._get_text is not None:
                text = self._get_text()
                if text is not None:
                    _win_set_text(text)

        def _on_release(self, key: object) -> None:  # pragma: no cover
            from pynput import keyboard as kb

            if key in (kb.Key.ctrl, kb.Key.ctrl_l, kb.Key.ctrl_r):
                self._ctrl_held = False
            elif key in (kb.Key.shift, kb.Key.shift_l, kb.Key.shift_r):
                self._shift_held = False

        def start(self, get_text: Callable[[], str | None]) -> None:  # pragma: no cover
            """Start the key listener.

            Args:
                get_text: Callable that returns the protected text, or ``None``
                    if the guard is inactive.
            """
            from pynput import keyboard as kb

            self._get_text = get_text
            self._ctrl_held = False
            self._shift_held = False
            self._listener = kb.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=False,
            )
            self._listener.start()

        def stop(self) -> None:  # pragma: no cover
            """Stop the key listener."""
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
            self._get_text = None

    # -----------------------------------------------------------------------
    # ClipboardGuard — public API
    # -----------------------------------------------------------------------

    class ClipboardGuard:
        """Dual-layer clipboard protection (Windows only).

        Layer 1: Hidden Win32 window monitors WM_CLIPBOARDUPDATE and restores
            the protected text on any clipboard change (< 1 ms reaction time).
        Layer 2: pynput WH_KEYBOARD_LL hook intercepts Ctrl+V / Shift+Insert
            and pre-loads the clipboard before the OS dispatches the keystroke
            (0 ms gap between key press and protected paste).

        Args:
            config: Optional :class:`~press.config.HoldConfig` to control which
                layers are enabled.  When ``None``, both layers are enabled.
            on_conflict: Called after the guard auto-releases because another
                application kept rewriting the clipboard (restore storm).

        Usage::

            guard = ClipboardGuard()
            guard.engage("text to protect")
            # ... user works, clipboard is defended ...
            guard.release()
        """

        def __init__(
            self,
            config: object | None = None,
            *,
            on_conflict: Callable[[], None] | None = None,
        ) -> None:
            self._protected_text: str | None = None
            self._on_conflict = on_conflict
            # Resolve layer flags from config (if provided) or default to True
            self._layer1_enabled: bool = (
                bool(getattr(config, "monitor_clipboard", True)) if config is not None else True
            )
            self._layer2_enabled: bool = (
                bool(getattr(config, "intercept_paste_keys", True)) if config is not None else True
            )
            self._monitor = _ClipboardMonitorWindow(self._get_protected, self._handle_conflict)
            self._interceptor = _PasteInterceptor()

        def _handle_conflict(self) -> None:
            """Layer 1 detected a restore war with another clipboard tool.

            Runs on the monitor thread: stand down (release) so the two tools
            stop fighting, then let the owner surface a notification.
            """
            self.release()
            if self._on_conflict is not None:
                self._on_conflict()

        def _get_protected(self) -> str | None:
            return self._protected_text

        # ------------------------------------------------------------------
        # Layer wiring (split out so tests can patch them individually)

        def _start_layer1(self) -> None:
            if self._layer1_enabled:
                self._monitor.start()

        def _stop_layer1(self) -> None:
            if self._layer1_enabled:
                self._monitor.stop()

        def _start_layer2(self) -> None:
            if self._layer2_enabled:
                self._interceptor.start(self._get_protected)

        def _stop_layer2(self) -> None:
            if self._layer2_enabled:
                self._interceptor.stop()

        # ------------------------------------------------------------------
        # Public API

        def engage(self, text: str) -> None:
            """Activate clipboard protection for *text*.

            If already active, the protected text is updated and both layers
            are restarted so they reference the new text immediately.

            Args:
                text: The text to protect.
            """
            if self._protected_text is not None:
                # Already active — stop existing layers before re-arming
                self._stop_layer1()
                self._stop_layer2()

            self._protected_text = text
            self._start_layer1()
            self._start_layer2()

        def release(self) -> None:
            """Deactivate protection.  The clipboard is left as-is."""
            if self._protected_text is None:
                return
            self._stop_layer1()
            self._stop_layer2()
            self._protected_text = None

        @property
        def is_active(self) -> bool:
            """True while protection is engaged."""
            return self._protected_text is not None

        @property
        def protected_text(self) -> str | None:
            """The currently protected text, or ``None`` when inactive."""
            return self._protected_text

else:  # pragma: no cover — stubs; the win32 block above is the implementation

    def _win_get_text() -> str:
        raise OSError("Clipboard access is only supported on Windows")

    def _win_set_text(_text: str, *, sensitive: bool = False) -> None:  # noqa: ARG001
        raise OSError("Clipboard access is only supported on Windows")

    def _win_clear() -> None:
        raise OSError("Clipboard access is only supported on Windows")

    def _win_sequence_number() -> int:
        raise OSError("Clipboard access is only supported on Windows")

    def _win_clear_if_unchanged(_sequence_number: int) -> bool:
        raise OSError("Clipboard access is only supported on Windows")

    def _win_has_sensitive_marks() -> bool:
        raise OSError("Clipboard access is only supported on Windows")

    class ClipboardGuard:
        """Stub for non-Windows platforms — raises OSError on all methods."""

        is_active: bool = False
        protected_text: str | None = None

        def __init__(
            self,
            _config: object | None = None,
            *,
            on_conflict: object | None = None,  # noqa: ARG002 — API-compatible stub
        ) -> None:
            raise OSError("ClipboardGuard is only available on Windows")

        def engage(self, _text: str) -> None:
            raise OSError("ClipboardGuard is only available on Windows")

        def release(self) -> None:
            raise OSError("ClipboardGuard is only available on Windows")
