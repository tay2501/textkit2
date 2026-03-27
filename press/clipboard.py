"""Clipboard read/write via ctypes (Windows) with cross-platform fallback."""

import sys


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


def set_clipboard_text(text: str) -> None:
    """Write text to the system clipboard.

    Args:
        text: Text to place on the clipboard.

    Raises:
        RuntimeError: If clipboard access fails.
        OSError: On non-Windows platforms where clipboard access is unavailable.
    """
    if sys.platform == "win32":
        _win_set_text(text)
        return
    raise OSError("Clipboard access is only supported on Windows")


# ---------------------------------------------------------------------------
# Windows implementation via ctypes
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

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

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

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

    def _win_set_text(text: str) -> None:
        encoded = (text + "\x00").encode("utf-16-le")
        size = len(encoded)

        h_mem = _kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not h_mem:
            raise RuntimeError("Failed to allocate clipboard memory")
        ptr = _kernel32.GlobalLock(h_mem)
        if not ptr:
            _kernel32.GlobalFree(h_mem)
            raise RuntimeError("Failed to lock clipboard memory")
        try:
            ctypes.memmove(ptr, encoded, size)
        finally:
            _kernel32.GlobalUnlock(h_mem)

        if not _user32.OpenClipboard(None):
            _kernel32.GlobalFree(h_mem)
            raise RuntimeError("Failed to open clipboard")
        try:
            _user32.EmptyClipboard()
            _user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        finally:
            _user32.CloseClipboard()

else:

    def _win_get_text() -> str:  # type: ignore[misc]
        raise OSError("Clipboard access is only supported on Windows")

    def _win_set_text(text: str) -> None:  # type: ignore[misc]
        raise OSError("Clipboard access is only supported on Windows")
