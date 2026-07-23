"""Tests for the pure leader-key sequence resolver.

These exercise the resolution *rules* with no queue, no watcher thread, and no
pynput — which is the point of keeping :mod:`press.daemon._sequence` free of
I/O.  The listener wiring that drives this resolver is covered separately in
``test_daemon.py``.
"""

from __future__ import annotations

import pytest

from press.commands import hotkey_sequence_candidates
from press.daemon._sequence import SequenceResolver


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
        ],
    )
    def test_sequence_dispatches(self, typed: str, expected: str) -> None:
        assert _type(_resolver(), typed) == ("dispatch", expected)

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
