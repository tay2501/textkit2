"""Tests for the uuid CLI command (generator, like genpass)."""

import re
import uuid

import pytest

from press.__main__ import make_parser

UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def _run(*argv: str) -> tuple[int, str]:
    parser = make_parser()
    args = parser.parse_args(list(argv))
    return args.func(args), ""


class TestUuidCommand:
    def test_single_uuid4(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc, _ = _run("uuid")
        out = capsys.readouterr().out
        assert rc == 0
        assert UUID4_RE.match(out.strip())

    def test_output_is_valid_uuid(self, capsys: pytest.CaptureFixture[str]) -> None:
        _run("uuid")
        out = capsys.readouterr().out.strip()
        parsed = uuid.UUID(out)
        assert parsed.version == 4

    def test_count(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc, _ = _run("uuid", "-n", "5")
        lines = capsys.readouterr().out.strip().split("\n")
        assert rc == 0
        assert len(lines) == 5
        assert all(UUID4_RE.match(line) for line in lines)

    def test_each_uuid_unique(self, capsys: pytest.CaptureFixture[str]) -> None:
        _run("uuid", "-n", "10")
        lines = capsys.readouterr().out.strip().split("\n")
        assert len(set(lines)) == 10

    def test_upper(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc, _ = _run("uuid", "--upper")
        out = capsys.readouterr().out.strip()
        assert rc == 0
        assert out == out.upper()
        assert uuid.UUID(out).version == 4

    def test_trailing_newline(self, capsys: pytest.CaptureFixture[str]) -> None:
        _run("uuid")
        assert capsys.readouterr().out.endswith("\n")

    def test_count_zero_rejected(self) -> None:
        parser = make_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["uuid", "-n", "0"])
