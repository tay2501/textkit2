"""Tests for underscore / hyphen separator conversion, and comma stripping (F-07)."""

from press.transforms.separator import hyphen_to_underscore, strip_commas, underscore_to_hyphen


class TestUnderscoreToHyphen:
    def test_basic(self) -> None:
        assert underscore_to_hyphen("USER_ID") == "USER-ID"

    def test_multiple(self) -> None:
        assert underscore_to_hyphen("FIRST_MIDDLE_LAST") == "FIRST-MIDDLE-LAST"

    def test_no_underscore(self) -> None:
        assert underscore_to_hyphen("USER-ID") == "USER-ID"

    def test_empty(self) -> None:
        assert underscore_to_hyphen("") == ""

    def test_preserves_case(self) -> None:
        assert underscore_to_hyphen("user_name") == "user-name"


class TestHyphenToUnderscore:
    def test_basic(self) -> None:
        assert hyphen_to_underscore("USER-ID") == "USER_ID"

    def test_multiple(self) -> None:
        assert hyphen_to_underscore("FIRST-MIDDLE-LAST") == "FIRST_MIDDLE_LAST"

    def test_no_hyphen(self) -> None:
        assert hyphen_to_underscore("USER_ID") == "USER_ID"

    def test_empty(self) -> None:
        assert hyphen_to_underscore("") == ""

    def test_preserves_case(self) -> None:
        assert hyphen_to_underscore("user-name") == "user_name"


class TestStripCommas:
    def test_integer_with_thousands_separator(self) -> None:
        assert strip_commas("1,234,567") == "1234567"

    def test_decimal_number(self) -> None:
        assert strip_commas("1,234.56") == "1234.56"

    def test_no_comma(self) -> None:
        assert strip_commas("1234567") == "1234567"

    def test_empty(self) -> None:
        assert strip_commas("") == ""

    def test_fullwidth_comma(self) -> None:
        assert strip_commas("1，234，567") == "1234567"

    def test_mixed_ascii_and_fullwidth(self) -> None:
        assert strip_commas("1,234，567") == "1234567"

    def test_comma_only(self) -> None:
        assert strip_commas(",") == ""

    def test_text_with_comma(self) -> None:
        assert strip_commas("hello, world") == "hello world"

    def test_multiline(self) -> None:
        assert strip_commas("1,000\n2,000\n3,000") == "1000\n2000\n3000"

    def test_negative_number(self) -> None:
        assert strip_commas("-1,234,567") == "-1234567"
