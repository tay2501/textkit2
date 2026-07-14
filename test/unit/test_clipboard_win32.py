"""Failure-path and sensitive-marking tests for the Win32 clipboard code.

EmptyClipboard / SetClipboardData can genuinely fail (RDP sessions, clipboard
managers or Office holding the clipboard).  A failure must raise — never
report success while the old clipboard content is still in place — and must
free the GlobalAlloc'd buffer, whose ownership only passes to the system when
SetClipboardData succeeds.

``sensitive=True`` must set the Win+V history / Cloud Clipboard exclusion
formats, and must wipe the clipboard if the marking fails: a secret never
sits on the clipboard unmarked.
"""

from __future__ import annotations

import ctypes

import pytest

_FAKE_HANDLE = 0xBEEF
_CF_UNICODETEXT = 13


class _FakeKernel32:
    """Stand-in kernel32 backing GlobalLock with real writable memory."""

    def __init__(self) -> None:
        self._bufs: dict[int, ctypes.Array[ctypes.c_char]] = {}
        self._next_handle = _FAKE_HANDLE
        self.freed: list[int] = []

    def GlobalAlloc(self, _flags: int, size: int) -> int:
        handle = self._next_handle
        self._next_handle += 1
        self._bufs[handle] = ctypes.create_string_buffer(size)
        return handle

    def GlobalLock(self, handle: int) -> int:
        return ctypes.addressof(self._bufs[handle])

    def GlobalUnlock(self, _handle: int) -> int:
        return 1

    def GlobalFree(self, handle: int) -> int:
        self.freed.append(handle)
        return 0


class _FakeUser32:
    """Stand-in user32 with scriptable failure modes."""

    def __init__(self) -> None:
        self._empty_ok = True
        self._set_ok = True
        self._register_ok = True
        self._formats: dict[str, int] = {}
        self.set_calls: list[int] = []  # formats passed to SetClipboardData
        self.empty_calls = 0
        self.closed = 0

    def OpenClipboard(self, _hwnd: object) -> int:
        return 1

    def EmptyClipboard(self) -> int:
        self.empty_calls += 1
        return 1 if self._empty_ok else 0

    def SetClipboardData(self, fmt: int, handle: int) -> int:
        if not self._set_ok:
            return 0
        self.set_calls.append(fmt)
        return handle

    def RegisterClipboardFormatW(self, name: str) -> int:
        if not self._register_ok:
            return 0
        return self._formats.setdefault(name, 0xC000 + len(self._formats))

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

    def test_empty_clipboard_failure_raises_before_allocating(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        from press.clipboard import _win_set_text

        u32, k32 = fakes
        u32._empty_ok = False
        with pytest.raises(RuntimeError, match="empty clipboard"):
            _win_set_text("abc")
        assert k32.freed == []  # nothing was allocated yet
        assert u32.set_calls == []
        assert u32.closed == 1

    def test_success_leaves_ownership_with_the_system(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        from press.clipboard import _win_set_text

        u32, k32 = fakes
        _win_set_text("abc")
        assert k32.freed == []  # the system owns the memory after success
        assert u32.set_calls == [_CF_UNICODETEXT]
        assert u32.closed == 1


@pytest.mark.windows_only
class TestSensitiveClipboardMarking:
    def test_sensitive_sets_all_exclusion_formats(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        from press.clipboard import _SENSITIVE_FORMATS, _win_set_text

        u32, _ = fakes
        _win_set_text("hunter2", sensitive=True)
        assert u32.set_calls[0] == _CF_UNICODETEXT
        assert len(u32.set_calls) == 1 + len(_SENSITIVE_FORMATS)
        assert set(u32._formats) == set(_SENSITIVE_FORMATS)

    def test_default_write_sets_only_the_text_format(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        from press.clipboard import _win_set_text

        u32, _ = fakes
        _win_set_text("plain")
        assert u32.set_calls == [_CF_UNICODETEXT]

    def test_marking_failure_wipes_the_clipboard(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        """The secret must not stay on the clipboard without exclusion marks."""
        from press.clipboard import _win_set_text

        u32, _ = fakes
        u32._register_ok = False
        with pytest.raises(RuntimeError, match="register clipboard format"):
            _win_set_text("hunter2", sensitive=True)
        assert u32.empty_calls == 2  # initial empty + the wipe on failure
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
