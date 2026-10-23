"""Tests for press genpass — secure password generation command."""

import os
import string
import subprocess
import sys

import pytest

from press.genpass import DEFAULT_LENGTH, generate_password

# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


class TestGeneratePassword:
    def test_default_length(self) -> None:
        pw = generate_password()
        assert len(pw) == DEFAULT_LENGTH

    def test_default_length_is_at_least_16(self) -> None:
        # NIST SP 800-63B minimum for memorized secrets is 8;
        # 16+ is considered strong for generated passwords.
        assert DEFAULT_LENGTH >= 16

    def test_custom_length(self) -> None:
        pw = generate_password(length=8)
        assert len(pw) == 8

    def test_length_one(self) -> None:
        pw = generate_password(length=1)
        assert len(pw) == 1

    def test_length_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="length"):
            generate_password(length=0)

    def test_negative_length_raises(self) -> None:
        with pytest.raises(ValueError, match="length"):
            generate_password(length=-5)

    # --- character set without symbols ---

    def test_no_symbols_by_default(self) -> None:
        valid = set(string.ascii_letters + string.digits)
        for _ in range(50):
            pw = generate_password(length=30)
            assert all(c in valid for c in pw), f"unexpected char in: {pw!r}"

    def test_default_contains_only_alphanumeric(self) -> None:
        pw = generate_password(length=100)
        assert pw.isascii()
        assert all(c.isalnum() for c in pw)

    # --- character set with symbols ---

    def test_symbols_flag_chars_within_extended_set(self) -> None:
        extended = set(string.ascii_letters + string.digits + string.punctuation)
        for _ in range(50):
            pw = generate_password(length=30, symbols=True)
            assert all(c in extended for c in pw), f"unexpected char in: {pw!r}"

    def test_symbols_flag_statistically_includes_symbol(self) -> None:
        # P(no symbol in 60 chars from 94-char set) = (62/94)^60 ≈ 2e-7 — negligible
        pw = generate_password(length=60, symbols=True)
        assert any(c in string.punctuation for c in pw)

    # --- distribution / entropy ---

    def test_long_password_contains_all_char_classes(self) -> None:
        # P(missing any class in 200 chars) is astronomically small
        pw = generate_password(length=200)
        assert any(c.isupper() for c in pw)
        assert any(c.islower() for c in pw)
        assert any(c.isdigit() for c in pw)

    def test_consecutive_calls_produce_different_output(self) -> None:
        # P(collision for two 20-char alphanumeric passwords) ≈ 62^{-20} ≈ 0
        results = {generate_password() for _ in range(5)}
        assert len(results) == 5

    # --- type safety ---

    def test_returns_str(self) -> None:
        assert isinstance(generate_password(), str)

    def test_output_is_ascii(self) -> None:
        pw = generate_password(length=50, symbols=True)
        assert pw.isascii()


# ---------------------------------------------------------------------------
# CLI integration tests (no clipboard required — subprocess captures stdout)
# ---------------------------------------------------------------------------

_ENV = {**os.environ, "PYTHONUTF8": "1"}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "press", "genpass", *args],
        capture_output=True,
        text=True,
        env=_ENV,
    )


class TestGenpassCLI:
    def test_exits_zero(self) -> None:
        assert _run().returncode == 0

    def test_default_outputs_20_chars_to_stdout(self) -> None:
        result = _run()
        assert len(result.stdout) == DEFAULT_LENGTH

    def test_custom_length_flag(self) -> None:
        result = _run("-L", "12")
        assert result.returncode == 0
        assert len(result.stdout) == 12

    def test_long_form_length_flag(self) -> None:
        result = _run("--length", "8")
        assert result.returncode == 0
        assert len(result.stdout) == 8

    def test_alias_gp_works(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "press", "gp"],
            capture_output=True,
            text=True,
            env=_ENV,
        )
        assert result.returncode == 0
        assert len(result.stdout) == DEFAULT_LENGTH

    def test_default_output_alphanumeric_only(self) -> None:
        result = _run("-L", "60")
        pw = result.stdout
        valid = set(string.ascii_letters + string.digits)
        assert all(c in valid for c in pw), f"unexpected char: {pw!r}"

    def test_symbols_flag_allows_punctuation(self) -> None:
        # Run with length 60 so at least one symbol is statistically certain
        result = _run("-L", "60", "-y")
        assert result.returncode == 0
        pw = result.stdout
        assert len(pw) == 60
        extended = set(string.ascii_letters + string.digits + string.punctuation)
        assert all(c in extended for c in pw)

    def test_length_zero_exits_nonzero(self) -> None:
        assert _run("-L", "0").returncode != 0

    def test_length_negative_exits_nonzero(self) -> None:
        assert _run("-L", "-1").returncode != 0

    def test_quiet_suppresses_stderr(self) -> None:
        result = _run("-q")
        assert result.returncode == 0
        assert result.stderr == ""

    def test_no_trailing_newline(self) -> None:
        # Output is raw password only — no newline added (piping-friendly)
        result = _run("-L", "10")
        assert "\n" not in result.stdout
        assert len(result.stdout) == 10

    def test_no_copy_flag_exits_zero(self) -> None:
        # --no-copy suppresses auto-clipboard write; stdout output is unaffected
        result = _run("--no-copy")
        assert result.returncode == 0
        assert len(result.stdout) == DEFAULT_LENGTH

    def test_no_copy_with_length(self) -> None:
        result = _run("--no-copy", "-L", "8")
        assert result.returncode == 0
        assert len(result.stdout) == 8

    def test_long_symbols_flag(self) -> None:
        result = _run("--symbols", "-L", "8")
        assert result.returncode == 0
        assert len(result.stdout) == 8

    @pytest.mark.parametrize("old", ["-n", "-N", "-s", "--no-clip", "--clip-out"])
    def test_old_flags_are_gone(self, old: str) -> None:
        # -n/-s were not pwgen/KeePassXC spellings; -s in keepassxc-cli means
        # "only special characters", the opposite of press's additive flag.
        assert _run(old, "8").returncode == 2


class TestGenpassCopyFlag:
    """``-C/--copy`` and ``--no-copy`` override the TTY auto-copy; unset = auto."""

    def _parse(self, *argv: str) -> object:
        from press.__main__ import make_parser

        return make_parser().parse_args(["genpass", *argv]).copy

    def test_default_is_auto(self) -> None:
        assert self._parse() is None

    @pytest.mark.parametrize("flag", ["-C", "--copy"])
    def test_copy(self, flag: str) -> None:
        assert self._parse(flag) is True

    def test_no_copy(self) -> None:
        assert self._parse("--no-copy") is False


# ---------------------------------------------------------------------------
# Clipboard-history exclusion (sensitive marking)
# ---------------------------------------------------------------------------


class TestGenpassSensitiveClipboard:
    """Passwords must never land in Win+V history or Cloud Clipboard sync."""

    def test_clipboard_write_is_marked_sensitive(self, capsys: pytest.CaptureFixture[str]) -> None:
        from unittest.mock import patch

        from press.__main__ import make_parser

        with patch("press.clipboard.set_clipboard_text") as set_text:
            args = make_parser().parse_args(["genpass", "-C", "-L", "12"])
            assert args.func(args) == 0

        assert set_text.call_args.kwargs.get("sensitive") is True
        capsys.readouterr()  # swallow the generated password


# ---------------------------------------------------------------------------
# Conditional auto-clear (--clear-after)
# ---------------------------------------------------------------------------


class TestGenpassClearAfter:
    """--clear-after wipes the clipboard only while it still holds the password."""

    def test_waits_then_clears_when_unchanged(self, capsys: pytest.CaptureFixture[str]) -> None:
        from unittest.mock import patch

        from press.__main__ import make_parser

        with (
            patch("press.clipboard.set_clipboard_text"),
            patch("press.clipboard.get_clipboard_sequence_number", return_value=7),
            patch("press.clipboard.clear_clipboard_if_unchanged", return_value=True) as clear,
            patch("time.sleep") as sleep,
        ):
            args = make_parser().parse_args(["genpass", "-C", "-L", "8", "--clear-after", "5"])
            assert args.func(args) == 0

        sleep.assert_called_once_with(5)
        clear.assert_called_once_with(7)
        assert "clipboard cleared" in capsys.readouterr().err

    def test_reports_when_another_app_changed_the_clipboard(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from unittest.mock import patch

        from press.__main__ import make_parser

        with (
            patch("press.clipboard.set_clipboard_text"),
            patch("press.clipboard.get_clipboard_sequence_number", return_value=7),
            patch("press.clipboard.clear_clipboard_if_unchanged", return_value=False),
            patch("time.sleep"),
        ):
            args = make_parser().parse_args(["genpass", "-C", "-L", "8", "--clear-after", "5"])
            assert args.func(args) == 0

        assert "not cleared" in capsys.readouterr().err

    def test_quiet_suppresses_clear_messages(self, capsys: pytest.CaptureFixture[str]) -> None:
        from unittest.mock import patch

        from press.__main__ import make_parser

        with (
            patch("press.clipboard.set_clipboard_text"),
            patch("press.clipboard.get_clipboard_sequence_number", return_value=7),
            patch("press.clipboard.clear_clipboard_if_unchanged", return_value=True),
            patch("time.sleep"),
        ):
            args = make_parser().parse_args(
                ["genpass", "-C", "-q", "-L", "8", "--clear-after", "5"]
            )
            assert args.func(args) == 0

        assert capsys.readouterr().err == ""

    def test_warns_when_no_clipboard_write_happened(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from press.__main__ import make_parser

        args = make_parser().parse_args(["genpass", "--no-copy", "-L", "8", "--clear-after", "5"])
        assert args.func(args) == 0
        assert "--clear-after ignored" in capsys.readouterr().err

    def test_clear_failure_is_a_warning_not_an_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from unittest.mock import patch

        from press.__main__ import make_parser

        with (
            patch("press.clipboard.set_clipboard_text"),
            patch("press.clipboard.get_clipboard_sequence_number", return_value=7),
            patch(
                "press.clipboard.clear_clipboard_if_unchanged",
                side_effect=RuntimeError("boom"),
            ),
            patch("time.sleep"),
        ):
            args = make_parser().parse_args(["genpass", "-C", "-L", "8", "--clear-after", "5"])
            assert args.func(args) == 0

        assert "clipboard clear failed" in capsys.readouterr().err

    def test_negative_seconds_exits_nonzero(self) -> None:
        assert _run("--clear-after", "-1").returncode != 0

    def test_default_is_disabled_no_sleep(self) -> None:
        from unittest.mock import patch

        from press.__main__ import make_parser

        with (
            patch("press.clipboard.set_clipboard_text"),
            patch("time.sleep") as sleep,
        ):
            args = make_parser().parse_args(["genpass", "-C", "-L", "8"])
            assert args.func(args) == 0

        sleep.assert_not_called()
