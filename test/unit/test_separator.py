"""Tests for underscore / hyphen separator conversion (F-07)."""

from press.transforms.separator import hyphen_to_underscore, underscore_to_hyphen


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
