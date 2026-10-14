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
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

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
        self._sequence = 100
        self._formats: dict[str, int] = {}
        self._open_failures = 0  # OpenClipboard fails this many times first
        self.open_calls = 0
        self.open_owners: list[object] = []  # hWndNewOwner per OpenClipboard
        self.set_calls: list[int] = []  # formats passed to SetClipboardData
        self.empty_calls = 0
        self.closed = 0

    def GetClipboardSequenceNumber(self) -> int:
        return self._sequence

    def OpenClipboard(self, hwnd: object) -> int:
        self.open_calls += 1
        self.open_owners.append(hwnd)
        if self._open_failures:
            self._open_failures -= 1
            return 0
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
class TestSensitiveFormatNames:
    def test_clipboard_viewer_ignore_is_included(self) -> None:
        """The classic Ditto/ClipboardFusion opt-out convention must be set too."""
        from press.clipboard import _SENSITIVE_FORMATS

        assert "Clipboard Viewer Ignore" in _SENSITIVE_FORMATS

    def test_win_v_exclusion_formats_are_included(self) -> None:
        from press.clipboard import _SENSITIVE_FORMATS

        assert "ExcludeClipboardContentFromMonitorProcessing" in _SENSITIVE_FORMATS
        assert "CanIncludeInClipboardHistory" in _SENSITIVE_FORMATS
        assert "CanUploadToCloudClipboard" in _SENSITIVE_FORMATS


@pytest.mark.windows_only
class TestClearIfUnchanged:
    """Conditional auto-clear must never destroy someone else's clipboard."""

    def test_clears_when_sequence_unchanged(self, fakes: tuple[_FakeUser32, _FakeKernel32]) -> None:
        from press.clipboard import _win_clear_if_unchanged

        u32, _ = fakes
        assert _win_clear_if_unchanged(u32._sequence) is True
        assert u32.empty_calls == 1
        assert u32.closed == 1

    def test_leaves_clipboard_alone_when_sequence_changed(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        from press.clipboard import _win_clear_if_unchanged

        u32, _ = fakes
        assert _win_clear_if_unchanged(u32._sequence - 1) is False
        assert u32.empty_calls == 0  # another app's content stays untouched
        assert u32.closed == 1

    def test_empty_clipboard_failure_raises(self, fakes: tuple[_FakeUser32, _FakeKernel32]) -> None:
        from press.clipboard import _win_clear_if_unchanged

        u32, _ = fakes
        u32._empty_ok = False
        with pytest.raises(RuntimeError, match="empty clipboard"):
            _win_clear_if_unchanged(u32._sequence)
        assert u32.closed == 1

    def test_sequence_number_helper_returns_current_value(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        from press.clipboard import _win_sequence_number

        u32, _ = fakes
        u32._sequence = 4242
        assert _win_sequence_number() == 4242


@pytest.mark.windows_only
class TestWinClearFailurePath:
    def test_empty_clipboard_failure_raises(self, fakes: tuple[_FakeUser32, _FakeKernel32]) -> None:
        from press.clipboard import _win_clear

        u32, _ = fakes
        u32._empty_ok = False
        with pytest.raises(RuntimeError, match="empty clipboard"):
            _win_clear()
        assert u32.closed == 1


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    import time

    recorded: list[float] = []
    monkeypatch.setattr(time, "sleep", recorded.append)
    return recorded


@pytest.mark.windows_only
class TestOpenClipboardRetry:
    """OpenClipboard fails while another window holds the clipboard open.

    WM_CLIPBOARDUPDATE arrives while the writer (or Win+V history) may still
    hold it, so a single attempt dropped ClipboardGuard restores.  Every
    entry point must retry a bounded number of times before giving up.
    """

    def test_transient_failure_is_retried(
        self, fakes: tuple[_FakeUser32, _FakeKernel32], sleeps: list[float]
    ) -> None:
        from press import clipboard

        u32, _ = fakes
        u32._open_failures = 3
        clipboard._win_set_text("abc")
        assert u32.open_calls == 4
        assert sleeps == [clipboard._OPEN_RETRY_DELAY] * 3
        assert u32.set_calls == [_CF_UNICODETEXT]
        assert u32.closed == 1

    @pytest.mark.parametrize(
        "call",
        [
            lambda c: c._win_get_text(),
            lambda c: c._win_set_text("abc"),
            lambda c: c._win_clear(),
            lambda c: c._win_clear_if_unchanged(100),
        ],
        ids=["get", "set", "clear", "clear_if_unchanged"],
    )
    def test_persistent_failure_raises_after_bounded_retries(
        self,
        fakes: tuple[_FakeUser32, _FakeKernel32],
        sleeps: list[float],
        call: Callable[[ModuleType], object],
    ) -> None:
        from press import clipboard

        u32, _ = fakes
        u32._open_failures = 10_000
        with pytest.raises(RuntimeError, match="Failed to open clipboard"):
            call(clipboard)
        assert u32.open_calls == clipboard._OPEN_RETRIES
        assert len(sleeps) == clipboard._OPEN_RETRIES - 1  # no sleep after the last try
        assert u32.closed == 0  # never close a clipboard we did not open


@pytest.mark.windows_only
class TestClipboardOwner:
    """The guard writes as its monitor window so its own WM_CLIPBOARDUPDATE
    can be recognised by GetClipboardOwner; other writers stay ownerless."""

    def test_default_write_has_no_owner_window(
        self, fakes: tuple[_FakeUser32, _FakeKernel32]
    ) -> None:
        from press.clipboard import _win_set_text

        u32, _ = fakes
        _win_set_text("abc")
        assert u32.open_owners == [None]

    def test_owner_is_passed_to_open_clipboard(
        self, fakes: tuple[_FakeUser32, _FakeKernel32], sleeps: list[float]
    ) -> None:
        from press.clipboard import _win_set_text

        u32, _ = fakes
        u32._open_failures = 1
        _win_set_text("abc", owner=0x42)
        assert u32.open_owners == [0x42, 0x42]  # the retry keeps the owner
