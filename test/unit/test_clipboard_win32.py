"""Failure-path tests for the Win32 clipboard implementation.

EmptyClipboard / SetClipboardData can genuinely fail (RDP sessions, clipboard
managers or Office holding the clipboard).  A failure must raise — never
report success while the old clipboard content is still in place — and must
free the GlobalAlloc'd buffer, whose ownership only passes to the system when
SetClipboardData succeeds.
"""

from __future__ import annotations

import ctypes

import pytest

_FAKE_HANDLE = 0xBEEF


class _FakeKernel32:
    """Stand-in kernel32 backing GlobalLock with real writable memory."""

    def __init__(self) -> None:
        self._buf: ctypes.Array[ctypes.c_char] | None = None
        self.freed: list[int] = []

    def GlobalAlloc(self, _flags: int, size: int) -> int:
        self._buf = ctypes.create_string_buffer(size)
        return _FAKE_HANDLE

    def GlobalLock(self, _handle: int) -> int:
        assert self._buf is not None
        return ctypes.addressof(self._buf)

    def GlobalUnlock(self, _handle: int) -> int:
        return 1

    def GlobalFree(self, handle: int) -> int:
        self.freed.append(handle)
        return 0


class _FakeUser32:
    """Stand-in user32 with scriptable EmptyClipboard/SetClipboardData results."""

    def __init__(self, *, empty_ok: bool = True, set_ok: bool = True) -> None:
        self._empty_ok = empty_ok
        self._set_ok = set_ok
        self.closed = 0

    def OpenClipboard(self, _hwnd: object) -> int:
        return 1

    def EmptyClipboard(self) -> int:
        return 1 if self._empty_ok else 0

    def SetClipboardData(self, _fmt: int, handle: int) -> int:
        return handle if self._set_ok else 0

    def CloseClipboard(self) -> int:
        self.closed += 1
        return 1


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> tuple[_FakeUser32, _FakeKernel32]:
    from press import clipboard

    u32 = _FakeUser32()
    k32 = _FakeKernel32()
    monkeypatch.setattr(clipboard, "_user32", u32)
    monkeypatch.setattr(clipboard, "_kernel32", k32)
    return u32, k32


@pytest.mark.windows_only
class TestWinSetTextFailurePaths:
    def test_set_clipboard_data_failure_raises_and_frees(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        from press.clipboard import _win_set_text

        u32, k32 = fakes
        u32._set_ok = False
        with pytest.raises(RuntimeError, match="set clipboard data"):
            _win_set_text("abc")
        assert k32.freed == [_FAKE_HANDLE]  # ownership never passed to the system
        assert u32.closed == 1  # clipboard released even on failure

    def test_empty_clipboard_failure_raises_and_frees(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        from press.clipboard import _win_set_text

        u32, k32 = fakes
        u32._empty_ok = False
        with pytest.raises(RuntimeError, match="empty clipboard"):
            _win_set_text("abc")
        assert k32.freed == [_FAKE_HANDLE]
        assert u32.closed == 1

    def test_success_leaves_ownership_with_the_system(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        from press.clipboard import _win_set_text

        u32, k32 = fakes
        _win_set_text("abc")
        assert k32.freed == []  # the system owns the memory after success
        assert u32.closed == 1


@pytest.mark.windows_only
class TestWinClearFailurePath:
    def test_empty_clipboard_failure_raises(self, fakes: tuple[_FakeUser32, _FakeKernel32]) -> None:
        from press.clipboard import _win_clear

        u32, _ = fakes
        u32._empty_ok = False
        with pytest.raises(RuntimeError, match="empty clipboard"):
            _win_clear()
        assert u32.closed == 1
