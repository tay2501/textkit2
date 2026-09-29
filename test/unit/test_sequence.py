"""Tests for the pure leader-key sequence resolver.

These exercise the resolution *rules* with no queue, no watcher thread, and no
pynput — which is the point of keeping :mod:`press.daemon._sequence` free of
I/O.  The listener wiring that drives this resolver is covered separately in
``test_daemon.py``.
"""

from __future__ import annotations

import pytest

from press.commands import hotkey_sequence_candidates
from press.daemon._sequence import KeySuppression, SequenceResolver


def _resolver(bindings: dict[str, str] | None = None) -> SequenceResolver:
    return SequenceResolver(hotkey_sequence_candidates(), bindings or {})


def _type(resolver: SequenceResolver, text: str) -> tuple[str, ...] | None:
    """Feed *text* one character at a time, returning the first resolution."""
    for char in text:
        resolution = resolver.press(char)
        if resolution is not None:
            return resolution
    return None


class TestSequenceResolution:
    @pytest.mark.parametrize(
        ("typed", "expected"),
        [
            ("tm", "trim"),  # alias resolves to the canonical name
            ("count", "count"),  # full name
            ("up", "upper"),  # exact match whose only extension is the same command
            ("hal", "halfwidth"),  # unique prefix fires before the name is complete
            ("html-e", "html-encode"),  # hyphenated names are typeable
            ("ty", "type"),  # keystroke paste — two strokes, ahead of trim/title/tt
            ("nn", "strip-newlines"),  # newline removal — free two-key alias
        ],
    )
    def test_sequence_dispatches(self, typed: str, expected: str) -> None:
        assert _type(_resolver(), typed) == ("dispatch", expected)

    def test_strip_newlines_alias_leaves_the_sn_sequences_alone(self) -> None:
        """``nn`` was chosen over ``snl`` precisely to keep ``sn`` at two keys.

        A second ``sn…`` candidate would turn the exact match ``sn`` into a
        pending one, so ``snake`` would only fire after the inactivity timeout.
        """
        assert _type(_resolver(), "sn") == ("dispatch", "snake")
        assert _type(_resolver(), "sl") == ("dispatch", "slug")

    def test_type_does_not_lengthen_the_other_t_sequences(self) -> None:
        """Adding ``type``/``ty`` must not push ``tm`` or ``tt`` out to 3 keys."""
        assert _type(_resolver(), "tm") == ("dispatch", "trim")
        assert _type(_resolver(), "tt") == ("dispatch", "title")

    def test_ambiguous_prefix_keeps_collecting(self) -> None:
        resolver = _resolver()
        assert resolver.press("t") is None  # tm / tt / trim / title all start with t
        assert resolver.press("m") == ("dispatch", "trim")

    def test_exact_match_with_different_extension_is_pending(self) -> None:
        """``cr`` is a command *and* a prefix of ``crlf`` — it must not fire."""
        resolver = _resolver()
        assert resolver.press("c") is None
        assert resolver.press("r") is None
        assert _type(resolver, "lf") == ("dispatch", "crlf")

    def test_pending_match_commits_on_timeout(self) -> None:
        resolver = _resolver()
        _type(resolver, "cr")
        assert resolver.on_timeout() == ("dispatch", "cr")

    def test_pending_match_commits_on_confirm(self) -> None:
        resolver = _resolver()
        _type(resolver, "cr")
        assert resolver.confirm() == ("dispatch", "cr")

    def test_timeout_without_pending_is_plain_timeout(self) -> None:
        resolver = _resolver()
        resolver.press("t")  # ambiguous, no exact match
        assert resolver.on_timeout() == ("timeout",)

    def test_unreachable_sequence_reports_unknown(self) -> None:
        assert _type(_resolver(), "tq") == ("unknown_key", "tq")

    def test_confirm_on_unknown_buffer_reports_it(self) -> None:
        resolver = _resolver()
        resolver.press("t")
        assert resolver.confirm() == ("unknown_key", "t")


class TestEditingKeys:
    def test_esc_cancels_silently(self) -> None:
        resolver = _resolver()
        resolver.press("t")
        assert resolver.press("esc") == ("timeout",)

    def test_backspace_edits_the_buffer(self) -> None:
        resolver = _resolver()
        resolver.press("t")
        assert resolver.press("backspace") is None
        assert resolver.buffer == ""
        assert _type(resolver, "wc") == ("dispatch", "count")

    def test_backspace_never_dispatches_on_an_exact_match(self) -> None:
        """Deleting back into a resolvable buffer must not fire a command.

        The user is editing; only fresh input, confirm, or the timeout commits.
        A hand-built candidate map states the rule directly instead of relying
        on the registry happening to contain such a shape.
        """
        resolver = SequenceResolver({"ab": "AB", "abc": "ABC", "abcd": "ABCD"}, {})
        assert resolver.press("a") is None
        assert resolver.press("b") is None  # exact match, but "abc"/"abcd" extend it
        assert resolver.press("c") is None  # still ambiguous between ABC and ABCD
        assert resolver.press("backspace") is None  # back to "ab" — must not fire
        assert resolver.on_timeout() == ("dispatch", "AB")

    def test_non_character_key_is_never_part_of_a_name(self) -> None:
        resolver = _resolver()
        assert resolver.press("f10") == ("unknown_key", "f10")

    def test_reset_clears_buffer_and_pending(self) -> None:
        resolver = _resolver()
        _type(resolver, "cr")
        resolver.reset()
        assert resolver.buffer == ""
        assert resolver.on_timeout() == ("timeout",)


class TestBindingsPrecedence:
    def test_user_binding_wins_on_the_first_key(self) -> None:
        resolver = _resolver(bindings={"k": "trim"})
        assert resolver.press("k") == ("dispatch", "trim")

    def test_shift_chord_binding(self) -> None:
        resolver = _resolver(bindings={"shift+z": "undo"})
        assert resolver.press("z", shift=True) == ("dispatch", "undo")

    def test_binding_only_applies_to_the_first_key(self) -> None:
        """Mid-sequence, a bound character is just another character."""
        resolver = _resolver(bindings={"m": "hold"})
        resolver.press("t")
        assert resolver.press("m") == ("dispatch", "trim")


class TestPipelineNames:
    def test_pipeline_name_is_typeable(self) -> None:
        resolver = SequenceResolver(hotkey_sequence_candidates(["xcleanup"]), {})
        assert _type(resolver, "xc") == ("dispatch", "xcleanup")

    def test_pipeline_cannot_shadow_a_registry_alias(self) -> None:
        """Registry names win — the same precedence CommandDispatcher applies."""
        candidates = hotkey_sequence_candidates(["tm"])
        assert candidates["tm"] == "trim"  # not the "tm" pipeline


# Virtual-key codes used by the suppression table below.
_VK_LSHIFT, _VK_LCONTROL, _VK_LMENU, _VK_LWIN = 0xA0, 0xA2, 0xA4, 0x5B
_VK_0, _VK_A, _VK_H = 0x30, 0x41, 0x48


class TestKeySuppression:
    """Which raw key events the leader listener may swallow.

    A low-level hook that swallows a key-up leaves Windows believing the key is
    still down (the hook runs before the async key state is updated), so the
    listener may only swallow events it owns: the presses it consumed and their
    matching releases.
    """

    @pytest.mark.parametrize("vk", [_VK_LSHIFT, _VK_LCONTROL, _VK_LMENU, _VK_LWIN, 0x10, 0x11])
    def test_modifiers_always_pass_through(self, vk: int) -> None:
        policy = KeySuppression()
        assert policy.should_suppress(vk, is_press=True) is False
        assert policy.should_suppress(vk, is_press=False) is False

    def test_prefix_keys_released_during_the_leader_pass_through(self) -> None:
        """Ctrl+Shift+0 are still held when the leader starts; their ups must reach the OS."""
        policy = KeySuppression()
        assert policy.should_suppress(_VK_0, is_press=False) is False
        assert policy.should_suppress(_VK_LCONTROL, is_press=False) is False
        assert policy.should_suppress(_VK_LSHIFT, is_press=False) is False

    def test_sequence_key_press_and_release_are_both_swallowed(self) -> None:
        policy = KeySuppression()
        assert policy.should_suppress(_VK_H, is_press=True) is True
        assert policy.should_suppress(_VK_H, is_press=False) is True

    def test_release_is_swallowed_only_once(self) -> None:
        policy = KeySuppression()
        policy.should_suppress(_VK_A, is_press=True)
        policy.should_suppress(_VK_A, is_press=False)
        assert policy.should_suppress(_VK_A, is_press=False) is False

    def test_autorepeat_press_is_released_once(self) -> None:
        policy = KeySuppression()
        policy.should_suppress(_VK_A, is_press=True)
        assert policy.should_suppress(_VK_A, is_press=True) is True  # auto-repeat
        assert policy.should_suppress(_VK_A, is_press=False) is True
        assert policy.should_suppress(_VK_A, is_press=False) is False

    def test_reset_forgets_presses_from_the_previous_leader(self) -> None:
        """A key consumed last time and held into the next leader was pressed before it."""
        policy = KeySuppression()
        policy.should_suppress(_VK_A, is_press=True)
        policy.reset()
        assert policy.should_suppress(_VK_A, is_press=False) is False
