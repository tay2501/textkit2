"""CLI integration tests for press __main__."""

import os
import subprocess
import sys
from pathlib import Path

# Path to the press package root
_PRESS_ROOT = Path(__file__).parent.parent.parent

# Force UTF-8 mode in child processes (critical on Japanese Windows / CP932)
_UTF8_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run press CLI via ``python -m press``; decode output as UTF-8."""
    cmd = [sys.executable, "-m", "press", *args]
    input_bytes = input_text.encode("utf-8") if input_text is not None else None
    raw = subprocess.run(
        cmd,
        input=input_bytes,
        capture_output=True,
        env=_UTF8_ENV,
        cwd=_PRESS_ROOT,
    )
    return subprocess.CompletedProcess(
        args=raw.args,
        returncode=raw.returncode,
        stdout=raw.stdout.decode("utf-8"),
        stderr=raw.stderr.decode("utf-8"),
    )


def _run_bytes(*args: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    """Run press CLI in binary mode to inspect raw line endings."""
    cmd = [sys.executable, "-m", "press", *args]
    return subprocess.run(
        cmd,
        input=input_bytes,
        capture_output=True,
        env=_UTF8_ENV,
        cwd=_PRESS_ROOT,
    )


# ---------------------------------------------------------------------------
# No-command / help
# ---------------------------------------------------------------------------


class TestNoCommand:
    def test_no_args_prints_help(self) -> None:
        result = _run()
        assert result.returncode == 0
        assert "press" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_version_flag(self) -> None:
        result = _run("--version")
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "press" in output


# ---------------------------------------------------------------------------
# halfwidth / hw
# ---------------------------------------------------------------------------


class TestHalfwidth:
    def test_stdin_to_stdout(self) -> None:
        result = _run("halfwidth", input_text="ＡＢＣＤ１２３")
        assert result.returncode == 0
        assert result.stdout.strip() == "ABCD123"

    def test_alias_hw(self) -> None:
        result = _run("hw", input_text="ＡＢＣＤ")
        assert result.returncode == 0
        assert result.stdout.strip() == "ABCD"

    def test_positional_input(self) -> None:
        result = _run("halfwidth", "ＨＥＬＬＯ")
        assert result.returncode == 0
        assert result.stdout.strip() == "HELLO"

    def test_verbose_writes_to_stderr(self) -> None:
        result = _run("halfwidth", "--verbose", input_text="Ａ")
        assert result.returncode == 0
        assert result.stdout.strip() == "A"
        assert "before" in result.stderr
        assert "after" in result.stderr

    def test_quiet_suppresses_stderr(self) -> None:
        result = _run("halfwidth", "--verbose", "--quiet", input_text="Ａ")
        assert result.returncode == 0
        assert result.stderr == ""


# ---------------------------------------------------------------------------
# fullwidth / fw
# ---------------------------------------------------------------------------


class TestFullwidth:
    def test_stdin_to_stdout(self) -> None:
        result = _run("fullwidth", input_text="ABC123")
        assert result.returncode == 0
        assert result.stdout.strip() == "ＡＢＣ１２３"

    def test_alias_fw(self) -> None:
        result = _run("fw", input_text="abc")
        assert result.returncode == 0
        assert result.stdout.strip() == "ａｂｃ"


# ---------------------------------------------------------------------------
# normalize / norm
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_collapses_spaces(self) -> None:
        result = _run("normalize", input_text="hello   world")
        assert result.returncode == 0
        assert result.stdout.strip() == "hello world"

    def test_alias_norm(self) -> None:
        result = _run("norm", input_text="  a  b  ")
        assert result.returncode == 0
        assert result.stdout.strip() == "a b"


# ---------------------------------------------------------------------------
# crlf / lf / cr  (binary mode to inspect raw bytes)
# ---------------------------------------------------------------------------


class TestLineEndings:
    def test_crlf(self) -> None:
        result = _run_bytes("crlf", input_bytes=b"a\nb\n")
        assert result.returncode == 0
        assert b"\r\n" in result.stdout

    def test_lf(self) -> None:
        result = _run_bytes("lf", input_bytes=b"a\r\nb\r\n")
        assert result.returncode == 0
        assert b"\r" not in result.stdout

    def test_cr(self) -> None:
        result = _run_bytes("cr", input_bytes=b"a\nb\n")
        assert result.returncode == 0
        # Strip the final trailing LF added after CR-only content
        content = result.stdout.rstrip(b"\n")
        assert b"\r" in content
        assert b"\n" not in content


# ---------------------------------------------------------------------------
# underscore / hyphen
# ---------------------------------------------------------------------------


class TestSeparators:
    def test_underscore(self) -> None:
        result = _run("underscore", input_text="foo-bar-baz")
        assert result.returncode == 0
        assert result.stdout.strip() == "foo_bar_baz"

    def test_alias_us(self) -> None:
        result = _run("us", input_text="a-b")
        assert result.returncode == 0
        assert result.stdout.strip() == "a_b"

    def test_hyphen(self) -> None:
        result = _run("hyphen", input_text="foo_bar_baz")
        assert result.returncode == 0
        assert result.stdout.strip() == "foo-bar-baz"

    def test_alias_hy(self) -> None:
        result = _run("hy", input_text="a_b")
        assert result.returncode == 0
        assert result.stdout.strip() == "a-b"


# ---------------------------------------------------------------------------
# sql-in / sq
# ---------------------------------------------------------------------------


class TestSqlIn:
    def test_basic(self) -> None:
        result = _run("sql-in", input_text="foo\nbar\nbaz\n")
        assert result.returncode == 0
        assert result.stdout.strip() == "'foo','bar','baz'"

    def test_alias_sq(self) -> None:
        result = _run("sq", input_text="a\nb\n")
        assert result.returncode == 0
        assert result.stdout.strip() == "'a','b'"

    def test_wrap_option(self) -> None:
        result = _run("sql-in", "--wrap", input_text="a\nb\n")
        assert result.returncode == 0
        assert result.stdout.strip() == "('a','b')"

    def test_quote_char_option(self) -> None:
        result = _run("sql-in", "--quote-char", '"', input_text="a\nb\n")
        assert result.returncode == 0
        assert result.stdout.strip() == '"a","b"'

    def test_empty_input_returns_exit_1(self) -> None:
        result = _run("sql-in", input_text="\n\n")
        assert result.returncode == 1

    def test_fallback_on_empty(self) -> None:
        result = _run("sql-in", "--fallback", input_text="\n\n")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# unicode-decode / unicode-encode
# ---------------------------------------------------------------------------


class TestUnicodeEscape:
    def test_decode(self) -> None:
        result = _run("unicode-decode", input_text=r"\u3053\u3093\u306b\u3061\u306f")
        assert result.returncode == 0
        assert result.stdout.strip() == "こんにちは"

    def test_alias_ud(self) -> None:
        result = _run("ud", input_text=r"\u0041")
        assert result.returncode == 0
        assert result.stdout.strip() == "A"

    def test_encode(self) -> None:
        result = _run("unicode-encode", input_text="こ")
        assert result.returncode == 0
        assert "\\u3053" in result.stdout

    def test_alias_ue(self) -> None:
        result = _run("ue", input_text="A")
        assert result.returncode == 0
        assert "A" in result.stdout  # ASCII preserved as-is

    def test_decode_failure_returns_exit_1(self) -> None:
        result = _run("unicode-decode", input_text="\\uXXXX")
        assert result.returncode == 1

    def test_decode_failure_with_fallback(self) -> None:
        result = _run("unicode-decode", "--fallback", input_text="\\uXXXX")
        assert result.returncode == 0
        assert "\\uXXXX" in result.stdout


# ---------------------------------------------------------------------------
# html-decode / hd
# ---------------------------------------------------------------------------


class TestHtmlDecode:
    def test_basic(self) -> None:
        result = _run("html-decode", input_text="&lt;div&gt;&amp;")
        assert result.returncode == 0
        assert result.stdout.strip() == "<div>&"

    def test_alias_hd(self) -> None:
        result = _run("hd", input_text="&amp;")
        assert result.returncode == 0
        assert result.stdout.strip() == "&"


# ---------------------------------------------------------------------------
# daemon (stub)
# ---------------------------------------------------------------------------


class TestDaemonStatus:
    def test_daemon_status_not_running(self) -> None:
        result = _run("daemon", "status")
        assert result.returncode == 1
        assert "not running" in result.stdout.lower()
