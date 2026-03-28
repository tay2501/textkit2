"""Tests for JSON formatting transforms (F-21, F-22)."""

import json

import pytest

from press.transforms.json_fmt import json_compress, json_format


class TestJsonFormat:
    def test_simple_object(self) -> None:
        result = json_format('{"a":1,"b":2}')
        assert result == '{\n  "a": 1,\n  "b": 2\n}'

    def test_simple_array(self) -> None:
        result = json_format("[1, 2, 3]")
        assert result == "[\n  1,\n  2,\n  3\n]"

    def test_custom_indent(self) -> None:
        result = json_format('{"a":1}', indent=4)
        assert result == '{\n    "a": 1\n}'

    def test_already_formatted(self) -> None:
        # Reformatting should produce the same canonical output
        formatted = '{\n  "a": 1,\n  "b": 2\n}'
        assert json_format(formatted) == formatted

    def test_japanese_not_escaped(self) -> None:
        result = json_format('{"key":"日本語"}')
        assert "日本語" in result

    def test_nested(self) -> None:
        result = json_format('{"a":{"b":1}}')
        parsed = json.loads(result)
        assert parsed == {"a": {"b": 1}}

    def test_invalid_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid JSON"):
            json_format("invalid")

    def test_empty_object(self) -> None:
        assert json_format("{}") == "{}"

    def test_empty_array(self) -> None:
        assert json_format("[]") == "[]"

    def test_whitespace_input(self) -> None:
        result = json_format('{ "a" :  1 , "b":2 }')
        assert result == '{\n  "a": 1,\n  "b": 2\n}'


class TestJsonCompress:
    def test_simple_object(self) -> None:
        result = json_compress('{ "a": 1, "b": 2 }')
        assert result == '{"a":1,"b":2}'

    def test_simple_array(self) -> None:
        result = json_compress("[ 1 , 2 , 3 ]")
        assert result == "[1,2,3]"

    def test_already_compact(self) -> None:
        compact = '{"a":1,"b":2}'
        assert json_compress(compact) == compact

    def test_japanese_not_escaped(self) -> None:
        result = json_compress('{"key": "日本語"}')
        assert "日本語" in result
        assert result == '{"key":"日本語"}'

    def test_nested(self) -> None:
        result = json_compress('{"a": {"b": 1}}')
        assert result == '{"a":{"b":1}}'

    def test_invalid_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid JSON"):
            json_compress("not json")

    def test_empty_object(self) -> None:
        assert json_compress("{}") == "{}"

    def test_empty_array(self) -> None:
        assert json_compress("[]") == "[]"

    def test_whitespace_removed(self) -> None:
        result = json_compress('{"a" :  1}')
        assert " " not in result
