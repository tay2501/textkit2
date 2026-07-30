"""Tests for keystroke synthesis (``press.keystrokes``).

The planning half is a pure function, so the rules that actually decide whether
a paste survives — CRLF collapsing to one Enter, Tab staying a character rather
than a focus change, astral characters splitting into a surrogate pair — are
pinned as a table on every platform.

The Win32 half is exercised against a fake ``user32``: what matters is that
every planned event reaches ``SendInput`` in order, that a partial acceptance
raises instead of leaving half the text typed, and that a held modifier stops
the send before a single key is injected.
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any

import pytest

from press.keystrokes import VK_RETURN, KeyStroke, plan_keystrokes, type_text

_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004


# ---------------------------------------------------------------------------
# plan_keystrokes (pure)
# ---------------------------------------------------------------------------


class TestPlanKeystrokes:
    def test_empty_text_plans_nothing(self) -> None:
        assert plan_keystrokes("") == []

    def test_ascii_becomes_one_unicode_packet_per_character(self) -> None:
        assert plan_keystrokes("ab1") == [
            KeyStroke(0, ord("a")),
            KeyStroke(0, ord("b")),
            KeyStroke(0, ord("1")),
        ]

    @pytest.mark.parametrize("text", ["a\r\nb", "a\rb", "a\nb"])
    def test_every_line_ending_collapses_to_one_enter(self, text: str) -> None:
        """CRLF must not type Enter twice — the clipboard is usually CRLF."""
        assert plan_keystrokes(text) == [
            KeyStroke(0, ord("a")),
            KeyStroke(VK_RETURN, 0),
            KeyStroke(0, ord("b")),
        ]

    def test_newline_unicode_mode_sends_a_character(self) -> None:
        assert plan_keystrokes("a\nb", newline="unicode") == [
            KeyStroke(0, ord("a")),
            KeyStroke(0, 0x0A),
            KeyStroke(0, ord("b")),
        ]

    def test_newline_skip_mode_drops_the_line_break(self) -> None:
        assert plan_keystrokes("a\nb", newline="skip") == [
            KeyStroke(0, ord("a")),
            KeyStroke(0, ord("b")),
        ]

    def test_tab_is_a_character_not_a_focus_change(self) -> None:
        """VK_TAB would move focus between controls; U+0009 inserts a tab."""
        (stroke,) = plan_keystrokes("\t")
        assert stroke == KeyStroke(0, 0x09)

    def test_astral_character_splits_into_a_surrogate_pair(self) -> None:
        """wScan is 16 bits, so U+1F600 travels as D83D DE00."""
        assert plan_keystrokes("\U0001f600") == [
            KeyStroke(0, 0xD83D),
            KeyStroke(0, 0xDE00),
        ]

    def test_japanese_text_stays_one_packet_per_character(self) -> None:
        assert plan_keystrokes("あ漢") == [KeyStroke(0, 0x3042), KeyStroke(0, 0x6F22)]


# ---------------------------------------------------------------------------
# type_text guard rails (platform independent)
# ---------------------------------------------------------------------------


class TestTypeTextGuards:
    def test_empty_text_sends_nothing(self) -> None:
        assert type_text("") == 0

    def test_text_over_the_limit_is_refused(self) -> None:
        with pytest.raises(ValueError, match="the limit is 10"):
            type_text("x" * 11, max_chars=10)

    def test_limit_is_checked_before_the_platform_gate(self) -> None:
        """The refusal must be the same error everywhere, not an OSError race."""
        with pytest.raises(ValueError):
            type_text("x" * 11, max_chars=10)

    @pytest.mark.skipif(sys.platform == "win32", reason="non-Windows behaviour")
    def test_non_windows_raises_oserror(self) -> None:
        with pytest.raises(OSError, match="only supported on Windows"):
            type_text("a")


# ---------------------------------------------------------------------------
# Win32 send path
# ---------------------------------------------------------------------------


class _FakeUser32:
    """Stand-in user32 recording the INPUT arrays handed to SendInput."""

    def __init__(self, *, held_modifiers: tuple[int, ...] = (), accept: int | None = None) -> None:
        self._held = held_modifiers
        self._accept = accept  # None = accept everything
        self.batches: list[list[tuple[int, int, int]]] = []

    def GetAsyncKeyState(self, vk: int) -> int:
        return -0x8000 if vk in self._held else 0

    def SendInput(self, count: int, events: Any, _size: int) -> int:
        self.batches.append(
            [(events[i].ki.wVk, events[i].ki.wScan, events[i].ki.dwFlags) for i in range(count)]
        )
        return count if self._accept is None else self._accept

    @property
    def events(self) -> list[tuple[int, int, int]]:
        return [event for batch in self.batches for event in batch]


@pytest.fixture
def fake_user32(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Install a fake user32 and return a factory that swaps in variants."""

    def install(**kwargs: Any) -> _FakeUser32:
        import press.keystrokes as ks

        fake = _FakeUser32(**kwargs)
        monkeypatch.setattr(ks, "_user32", fake)
        return fake

    return install


@pytest.mark.windows_only
class TestWin32Send:
    def test_input_struct_matches_the_win32_abi(self) -> None:
        """A wrong sizeof(INPUT) makes SendInput fail with no useful error."""
        import press.keystrokes as ks

        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        assert ctypes.sizeof(ks._INPUT) == expected

    def test_each_character_is_sent_down_then_up_as_a_unicode_packet(
        self, fake_user32: Any
    ) -> None:
        fake = fake_user32()
        assert type_text("ab") == 2
        assert fake.events == [
            (0, ord("a"), _KEYEVENTF_UNICODE),
            (0, ord("a"), _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP),
            (0, ord("b"), _KEYEVENTF_UNICODE),
            (0, ord("b"), _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP),
        ]

    def test_newline_is_a_virtual_key_without_the_unicode_flag(self, fake_user32: Any) -> None:
        fake = fake_user32()
        type_text("\n")
        assert fake.events == [(VK_RETURN, 0, 0), (VK_RETURN, 0, _KEYEVENTF_KEYUP)]

    def test_long_text_is_split_into_chunks(self, fake_user32: Any) -> None:
        """Chunking is what keeps a slow target's message queue from overflowing."""
        fake = fake_user32()
        type_text("abcde", chunk_size=2, chunk_delay=0)
        assert [len(batch) for batch in fake.batches] == [4, 4, 2]
        assert len(fake.events) == 10  # 5 characters x (down + up)

    def test_partial_acceptance_raises(self, fake_user32: Any) -> None:
        """UIPI refusal must surface, not silently type half the text."""
        fake_user32(accept=1)
        with pytest.raises(RuntimeError, match="accepted 1/4"):
            type_text("ab")

    def test_held_modifier_blocks_the_send(self, fake_user32: Any, monkeypatch: Any) -> None:
        """Ctrl still down from the prefix chord would turn Enter into Ctrl+Enter."""
        import press.keystrokes as ks

        monkeypatch.setattr(ks, "_MODIFIER_TIMEOUT", 0.02)
        fake = fake_user32(held_modifiers=(0x11,))  # VK_CONTROL
        with pytest.raises(RuntimeError, match="modifier key still held"):
            type_text("a")
        assert fake.batches == []

    def test_released_modifier_lets_the_send_through(self, fake_user32: Any) -> None:
        fake = fake_user32(held_modifiers=())
        type_text("a")
        assert len(fake.events) == 2
