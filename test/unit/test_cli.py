"""CLI integration tests for press __main__."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

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
# Input routing
# ---------------------------------------------------------------------------


class TestInputRouting:
    def test_stdin_pipe_used_when_not_tty(self) -> None:
        # subprocess stdin is always a pipe (non-TTY), so piped text is used
        result = _run("upper", input_text="hello")
        assert result.returncode == 0
        assert result.stdout.strip() == "HELLO"

    def test_dash_sentinel_forces_stdin(self) -> None:
        # "-" as positional arg forces stdin even when clip-in is not set
        result = _run("upper", "-", input_text="hello")
        assert result.returncode == 0
        assert result.stdout.strip() == "HELLO"

    def test_positional_arg_takes_priority_over_pipe(self) -> None:
        result = _run("upper", "hello", input_text="ignored")
        assert result.returncode == 0
        assert result.stdout.strip() == "HELLO"


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
# collapse-whitespace
# ---------------------------------------------------------------------------


class TestCollapseWhitespace:
    def test_collapses_spaces(self) -> None:
        result = _run("collapse-whitespace", input_text="hello   world")
        assert result.returncode == 0
        assert result.stdout.strip() == "hello world"

    def test_drops_blank_lines(self) -> None:
        result = _run("collapse-whitespace", input_text="  a  b  \n\n   \nc")
        assert result.returncode == 0
        assert result.stdout == "a b\nc"

    @pytest.mark.parametrize("old", ["normalize", "norm"])
    def test_old_names_are_gone(self, old: str) -> None:
        assert _run(old, input_text="a").returncode == 2


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

    def test_strip_newlines(self) -> None:
        result = _run_bytes("strip-newlines", input_bytes=b"a\r\nb\nc\r")
        assert result.returncode == 0
        assert result.stdout == b"abc"

    def test_strip_newlines_alias_nn(self) -> None:
        result = _run_bytes("nn", input_bytes=b"a\nb\n")
        assert result.returncode == 0
        assert result.stdout == b"ab"

    @pytest.mark.parametrize("name", ["dos2unix", "unix2dos"])
    def test_no_dos2unix_aliases(self, name: str) -> None:
        # dos2unix strips a BOM and leaves lone CR alone; lf/crlf do neither,
        # so borrowing the tool's name would promise behaviour press lacks.
        assert _run(name, input_text="a").returncode == 2


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

    @pytest.mark.parametrize("old", ["underbar", "ub"])
    def test_old_aliases_are_gone(self, old: str) -> None:
        assert _run(old, input_text="a-b").returncode == 2

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
        assert result.stdout.strip() == "'bar','baz','foo'"

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
# unicode-unescape / unicode-escape
# ---------------------------------------------------------------------------


class TestUnicodeEscape:
    def test_unescape(self) -> None:
        result = _run("unicode-unescape", input_text=r"\u3053\u3093\u306b\u3061\u306f")
        assert result.returncode == 0
        assert result.stdout.strip() == "こんにちは"

    def test_alias_uu(self) -> None:
        result = _run("uu", input_text=r"\u0041")
        assert result.returncode == 0
        assert result.stdout.strip() == "A"

    def test_escape(self) -> None:
        result = _run("unicode-escape", input_text="こ")
        assert result.returncode == 0
        assert "\\u3053" in result.stdout

    def test_alias_ue(self) -> None:
        result = _run("ue", input_text="A")
        assert result.returncode == 0
        assert "A" in result.stdout  # ASCII preserved as-is

    def test_unescape_failure_returns_exit_1(self) -> None:
        result = _run("unicode-unescape", input_text="\\uXXXX")
        assert result.returncode == 1

    def test_unescape_failure_with_fallback(self) -> None:
        result = _run("unicode-unescape", "--fallback", input_text="\\uXXXX")
        assert result.returncode == 0
        assert "\\uXXXX" in result.stdout


# ---------------------------------------------------------------------------
# html-unescape / html-escape
# ---------------------------------------------------------------------------


class TestHtmlEscape:
    def test_basic(self) -> None:
        result = _run("html-unescape", input_text="&lt;div&gt;&amp;")
        assert result.returncode == 0
        assert result.stdout.strip() == "<div>&"

    def test_alias_hu(self) -> None:
        result = _run("hu", input_text="&amp;")
        assert result.returncode == 0
        assert result.stdout.strip() == "&"

    def test_escape_alias_he(self) -> None:
        result = _run("he", input_text="<a>")
        assert result.returncode == 0
        assert result.stdout == "&lt;a&gt;"

    @pytest.mark.parametrize(
        "old", ["html-decode", "html-encode", "hd", "unicode-decode", "unicode-encode", "ud"]
    )
    def test_old_names_are_gone(self, old: str) -> None:
        # hd is util-linux's `hexdump -C`; an alias named after a known tool
        # must mean what that tool does.
        assert _run(old, input_text="&amp;").returncode == 2


# ---------------------------------------------------------------------------
# trim
# ---------------------------------------------------------------------------


class TestTrim:
    def test_trailing_spaces(self) -> None:
        result = _run("trim", input_text="hello   \nworld   ")
        assert result.returncode == 0
        assert result.stdout == "hello\nworld"

    def test_alias_tm(self) -> None:
        result = _run("tm", input_text="hello   ")
        assert result.returncode == 0
        assert result.stdout.strip() == "hello"

    def test_strips_both_sides_by_default(self) -> None:
        # Same result as the hotkey: CLI and daemon transforms must agree.
        result = _run("trim", input_text="  hello  \n  world  ")
        assert result.returncode == 0
        assert result.stdout == "hello\nworld"

    def test_both_flag_is_gone(self) -> None:
        # Stripping both sides is the default; only --trailing changes it.
        assert _run("trim", "--both", input_text="  hello  ").returncode == 2

    def test_long_option_prefixes_are_rejected(self) -> None:
        # allow_abbrev=False: `--trail` must not silently mean --trailing,
        # or adding a new --trail… option later would change old scripts.
        assert _run("trim", "--trail", input_text="  hello  ").returncode == 2

    @pytest.mark.parametrize("flag", ["--trailing", "-t"])
    def test_trailing_flag_keeps_leading_whitespace(self, flag: str) -> None:
        result = _run("trim", flag, input_text="  hello  \n    world  ")
        assert result.returncode == 0
        assert result.stdout == "  hello\n    world"

    def test_empty_input(self) -> None:
        result = _run("trim", input_text="")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# dedupe
# ---------------------------------------------------------------------------


class TestDedupe:
    def test_basic(self) -> None:
        result = _run("dedupe", input_text="a\nb\na\nc")
        assert result.returncode == 0
        assert result.stdout.strip() == "a\nb\nc"

    def test_alias_dq_is_gone(self) -> None:
        assert _run("dq", input_text="a\na\nb").returncode == 2

    @pytest.mark.parametrize("flag", ["--ignore-case", "-i"])
    def test_ignore_case(self, flag: str) -> None:
        result = _run("dedupe", flag, input_text="Hello\nhello\nWorld")
        assert result.returncode == 0
        assert result.stdout.strip() == "Hello\nWorld"

    def test_adjacent(self) -> None:
        result = _run("dedupe", "--adjacent", input_text="a\na\nb\na")
        assert result.returncode == 0
        assert result.stdout.strip() == "a\nb\na"

    def test_adjacent_has_no_short_flag(self) -> None:
        assert _run("dedupe", "-a", input_text="a").returncode == 2

    def test_empty_input(self) -> None:
        result = _run("dedupe", input_text="")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# sort
# ---------------------------------------------------------------------------


class TestSort:
    def test_basic(self) -> None:
        result = _run("sort", input_text="banana\napple\ncherry")
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0].lower() == "apple"

    def test_alias_st(self) -> None:
        result = _run("st", input_text="b\na")
        assert result.returncode == 0
        assert result.stdout.strip() == "a\nb"

    @pytest.mark.parametrize("flag", ["--reverse", "-r"])
    def test_reverse(self, flag: str) -> None:
        result = _run("sort", flag, input_text="a\nb\nc")
        assert result.returncode == 0
        assert result.stdout.strip() == "c\nb\na"

    @pytest.mark.parametrize("flag", ["--numeric-sort", "-n"])
    def test_numeric(self, flag: str) -> None:
        result = _run("sort", flag, input_text="10\n2\n1")
        assert result.returncode == 0
        assert result.stdout.strip() == "1\n2\n10"

    def test_numeric_uses_leading_number_like_gnu_sort(self) -> None:
        # GNU sort -n: a line without a leading number compares as 0.
        result = _run("sort", "-n", input_text="10 apples\n2 pears\napple\n1")
        assert result.returncode == 0
        assert result.stdout == "apple\n1\n2 pears\n10 apples"

    @pytest.mark.parametrize("flag", ["--ignore-case", "-f"])
    def test_ignore_case(self, flag: str) -> None:
        result = _run("sort", flag, input_text="banana\nApple")
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0].lower() == "apple"

    def test_old_numeric_flag_is_gone(self) -> None:
        assert _run("sort", "--numeric", input_text="1").returncode == 2

    def test_empty_input(self) -> None:
        result = _run("sort", input_text="")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Unicode normalization (nfc / nfd / nfkc / nfkd)
# ---------------------------------------------------------------------------

# が in NFD: U+304B (か) + U+3099 (combining dakuten)
_GA_NFD = "が"
# が in NFC: U+304C (precomposed)
_GA_NFC = "が"


class TestUnicodeNorm:
    def test_nfc_stdin_to_stdout(self) -> None:
        result = _run("nfc", input_text=_GA_NFD)
        assert result.returncode == 0
        assert result.stdout.strip() == _GA_NFC

    def test_nfc_already_nfc_unchanged(self) -> None:
        result = _run("nfc", input_text=_GA_NFC)
        assert result.returncode == 0
        assert result.stdout.strip() == _GA_NFC

    def test_nfd_stdin_to_stdout(self) -> None:
        result = _run("nfd", input_text=_GA_NFC)
        assert result.returncode == 0
        assert result.stdout.strip() == _GA_NFD

    def test_nfkc_fullwidth_to_ascii(self) -> None:
        # full-width ABC -> ASCII ABC
        result = _run("nfkc", input_text="ＡＢＣ")
        assert result.returncode == 0
        assert result.stdout.strip() == "ABC"

    def test_nfkd_fullwidth_to_ascii(self) -> None:
        # full-width ABC -> ASCII ABC
        result = _run("nfkd", input_text="ＡＢＣ")
        assert result.returncode == 0
        assert result.stdout.strip() == "ABC"

    def test_nfc_empty_input(self) -> None:
        result = _run("nfc", input_text="")
        assert result.returncode == 0

    def test_nfkc_ligature(self) -> None:
        result = _run("nfkc", input_text="ﬁ")  # ﬁ
        assert result.returncode == 0
        assert result.stdout.strip() == "fi"


# ---------------------------------------------------------------------------
# daemon (stub)
# ---------------------------------------------------------------------------


class TestGroupWithoutAction:
    """``press <group>`` with no ACTION prints that group's help and exits 0.

    Run through ``python -m press`` on purpose: the help used to be produced
    by re-executing ``sys.argv[0]``, which is ``__main__.py`` in that mode
    and raised OSError on Windows.
    """

    @pytest.mark.parametrize("group", ["config", "daemon", "notify", "trace"])
    def test_prints_group_help(self, group: str) -> None:
        result = _run(group)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith(f"usage: press {group} ")
        assert "Traceback" not in result.stderr


class TestDaemonStatus:
    def test_daemon_status_not_running(self, tmp_path: Path) -> None:
        # Isolated APPDATA: `status` removes a stale PID file on Windows, and a
        # test must never touch the developer's real %APPDATA%\press state.
        # The stale file is planted on Windows only: elsewhere `status` asks
        # psutil, and PID 99999 may well be a live process on a CI runner.
        pid_file = tmp_path / "press" / "press.pid"
        if sys.platform == "win32":
            pid_file.parent.mkdir()
            pid_file.write_text("99999", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "press", "daemon", "status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**_UTF8_ENV, "APPDATA": str(tmp_path)},
            cwd=_PRESS_ROOT,
        )
        assert result.returncode == 1
        assert "not running" in result.stdout.lower()
        if sys.platform == "win32":
            assert not pid_file.exists()


# ---------------------------------------------------------------------------
# De facto flag and alias spellings (GNU coreutils, grep/ripgrep, jq, Python)
# ---------------------------------------------------------------------------


class TestDeFactoSpellings:
    def test_replace_grep_style_flags(self) -> None:
        result = _run("replace", "-e", "a", "-e", "c", "-r", "_", input_text="abc")
        assert result.returncode == 0
        assert result.stdout == "_b_"

    def test_replace_long_flags(self) -> None:
        result = _run(
            "replace",
            "--regexp",
            "1.5",
            "--replace",
            "9",
            "--fixed-strings",
            "--ignore-case",
            input_text="1.5 125",
        )
        assert result.returncode == 0
        assert result.stdout == "9 125"

    def test_replace_without_pattern_is_a_usage_error(self) -> None:
        result = _run("replace", "-r", "x", input_text="abc")
        assert result.returncode == 2
        assert "--regexp" in result.stderr

    @pytest.mark.parametrize("old", ["--pattern", "-p", "--repl", "--fixed"])
    def test_replace_old_flags_are_gone(self, old: str) -> None:
        assert _run("replace", "-e", "a", old, "b", input_text="a").returncode == 2

    def test_number_lines_gnu_nl_flags(self) -> None:
        result = _run(
            "number-lines",
            "--starting-line-number",
            "5",
            "-s",
            ": ",
            input_text="a\nb",
        )
        assert result.returncode == 0
        assert result.stdout == "5: a\n6: b"

    @pytest.mark.parametrize("old", ["--start", "--sep"])
    def test_number_lines_old_flags_are_gone(self, old: str) -> None:
        assert _run("number-lines", old, "1", input_text="a").returncode == 2

    @pytest.mark.parametrize("flag", ["-a", "--algorithm"])
    def test_hash_algorithm_flag(self, flag: str) -> None:
        result = _run("hash", flag, "md5", input_text="abc")
        assert result.returncode == 0
        assert result.stdout == "900150983cd24fb0d6963f7d28e17f72"

    def test_hash_old_flag_is_gone(self) -> None:
        assert _run("hash", "--algo", "md5", input_text="abc").returncode == 2

    @pytest.mark.parametrize("flag", ["-u", "--utc"])
    def test_unix_to_date_utc(self, flag: str) -> None:
        result = _run("unix-to-date", flag, input_text="0")
        assert result.returncode == 0
        assert result.stdout.startswith("1970-01-01T00:00:00")

    def test_unix_to_date_alias_ut(self) -> None:
        assert _run("ut", "-u", input_text="0").returncode == 0

    @pytest.mark.parametrize("old", ["u2d", "d2u"])
    def test_time_aliases_named_like_dos2unix_are_gone(self, old: str) -> None:
        # cygutils' u2d/d2u are unix2dos/dos2unix.
        assert _run(old, input_text="0").returncode == 2

    def test_json_compact_alias_jc(self) -> None:
        result = _run("jc", input_text='{ "a": 1 }')
        assert result.returncode == 0
        assert result.stdout == '{"a":1}'

    def test_json_compress_is_gone(self) -> None:
        assert _run("json-compress", input_text="{}").returncode == 2

    @pytest.mark.parametrize("indent", ["-1", "8"])
    def test_json_format_indent_is_bounded_like_jq(self, indent: str) -> None:
        assert _run("json-format", "--indent", indent, input_text="{}").returncode == 2

    def test_strip_commas_alias_scm(self) -> None:
        result = _run("scm", input_text="1,234")
        assert result.returncode == 0
        assert result.stdout == "1234"

    def test_strip_commas_alias_sc_is_gone(self) -> None:
        # sc is Windows' built-in service-control tool.
        assert _run("sc", input_text="1,234").returncode == 2

    @pytest.mark.parametrize("alias", ["tac", "rl"])
    def test_reverse_lines_aliases(self, alias: str) -> None:
        result = _run(alias, input_text="a\nb")
        assert result.returncode == 0
        assert result.stdout == "b\na"
