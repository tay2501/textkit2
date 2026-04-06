"""Tests for case conversion transforms (F-13 to F-21)."""

from press.transforms.case import (
    to_camel_case,
    to_capitalize,
    to_kebab_case,
    to_lower,
    to_pascal_case,
    to_snake_case,
    to_swapcase,
    to_title,
    to_upper,
)


class TestToSnakeCase:
    def test_camel_to_snake(self) -> None:
        assert to_snake_case("helloWorld") == "hello_world"

    def test_pascal_to_snake(self) -> None:
        assert to_snake_case("HelloWorld") == "hello_world"

    def test_kebab_to_snake(self) -> None:
        assert to_snake_case("hello-world") == "hello_world"

    def test_consecutive_uppercase(self) -> None:
        assert to_snake_case("HTTPResponse") == "http_response"

    def test_already_snake(self) -> None:
        assert to_snake_case("hello_world") == "hello_world"

    def test_single_word(self) -> None:
        assert to_snake_case("hello") == "hello"

    def test_empty(self) -> None:
        assert to_snake_case("") == ""

    def test_multiline(self) -> None:
        result = to_snake_case("helloWorld\nfooBar")
        assert result == "hello_world\nfoo_bar"

    def test_empty_line_preserved(self) -> None:
        result = to_snake_case("helloWorld\n\nfooBar")
        assert result == "hello_world\n\nfoo_bar"

    def test_pascal_case(self) -> None:
        assert to_snake_case("PascalCase") == "pascal_case"

    def test_https_server(self) -> None:
        assert to_snake_case("HTTPSServer") == "https_server"


class TestToCamelCase:
    def test_snake_to_camel(self) -> None:
        assert to_camel_case("hello_world") == "helloWorld"

    def test_kebab_to_camel(self) -> None:
        assert to_camel_case("hello-world") == "helloWorld"

    def test_already_camel(self) -> None:
        assert to_camel_case("helloWorld") == "helloWorld"

    def test_single_word(self) -> None:
        assert to_camel_case("hello") == "hello"

    def test_empty(self) -> None:
        assert to_camel_case("") == ""

    def test_multiline(self) -> None:
        result = to_camel_case("hello_world\nfoo_bar")
        assert result == "helloWorld\nfooBar"

    def test_empty_line_preserved(self) -> None:
        result = to_camel_case("hello_world\n\nfoo_bar")
        assert result == "helloWorld\n\nfooBar"

    def test_three_words(self) -> None:
        assert to_camel_case("foo_bar_baz") == "fooBarBaz"

    def test_from_pascal(self) -> None:
        assert to_camel_case("HelloWorld") == "helloWorld"


class TestToPascalCase:
    def test_snake_to_pascal(self) -> None:
        assert to_pascal_case("hello_world") == "HelloWorld"

    def test_kebab_to_pascal(self) -> None:
        assert to_pascal_case("hello-world") == "HelloWorld"

    def test_camel_to_pascal(self) -> None:
        assert to_pascal_case("helloWorld") == "HelloWorld"

    def test_already_pascal(self) -> None:
        assert to_pascal_case("HelloWorld") == "HelloWorld"

    def test_single_word(self) -> None:
        assert to_pascal_case("hello") == "Hello"

    def test_empty(self) -> None:
        assert to_pascal_case("") == ""

    def test_multiline(self) -> None:
        result = to_pascal_case("hello_world\nfoo_bar")
        assert result == "HelloWorld\nFooBar"

    def test_empty_line_preserved(self) -> None:
        result = to_pascal_case("hello_world\n\nfoo_bar")
        assert result == "HelloWorld\n\nFooBar"

    def test_three_words(self) -> None:
        assert to_pascal_case("foo_bar_baz") == "FooBarBaz"


class TestToKebabCase:
    def test_snake_to_kebab(self) -> None:
        assert to_kebab_case("hello_world") == "hello-world"

    def test_camel_to_kebab(self) -> None:
        assert to_kebab_case("helloWorld") == "hello-world"

    def test_pascal_to_kebab(self) -> None:
        assert to_kebab_case("HelloWorld") == "hello-world"

    def test_already_kebab(self) -> None:
        assert to_kebab_case("hello-world") == "hello-world"

    def test_single_word(self) -> None:
        assert to_kebab_case("hello") == "hello"

    def test_empty(self) -> None:
        assert to_kebab_case("") == ""

    def test_multiline(self) -> None:
        result = to_kebab_case("helloWorld\nfooBar")
        assert result == "hello-world\nfoo-bar"

    def test_empty_line_preserved(self) -> None:
        result = to_kebab_case("helloWorld\n\nfooBar")
        assert result == "hello-world\n\nfoo-bar"

    def test_consecutive_uppercase(self) -> None:
        assert to_kebab_case("HTTPResponse") == "http-response"

    def test_pascal_case(self) -> None:
        assert to_kebab_case("PascalCase") == "pascal-case"


class TestToUpper:
    def test_basic(self) -> None:
        assert to_upper("hello world") == "HELLO WORLD"

    def test_already_upper(self) -> None:
        assert to_upper("HELLO") == "HELLO"

    def test_mixed(self) -> None:
        assert to_upper("Hello World") == "HELLO WORLD"

    def test_empty(self) -> None:
        assert to_upper("") == ""

    def test_multiline(self) -> None:
        assert to_upper("hello\nworld") == "HELLO\nWORLD"

    def test_empty_line_preserved(self) -> None:
        assert to_upper("hello\n\nworld") == "HELLO\n\nWORLD"

    def test_numbers_unchanged(self) -> None:
        assert to_upper("hello123") == "HELLO123"


class TestToLower:
    def test_basic(self) -> None:
        assert to_lower("HELLO WORLD") == "hello world"

    def test_already_lower(self) -> None:
        assert to_lower("hello") == "hello"

    def test_mixed(self) -> None:
        assert to_lower("Hello World") == "hello world"

    def test_empty(self) -> None:
        assert to_lower("") == ""

    def test_multiline(self) -> None:
        assert to_lower("HELLO\nWORLD") == "hello\nworld"

    def test_empty_line_preserved(self) -> None:
        assert to_lower("HELLO\n\nWORLD") == "hello\n\nworld"

    def test_numbers_unchanged(self) -> None:
        assert to_lower("HELLO123") == "hello123"


class TestToTitle:
    def test_basic(self) -> None:
        assert to_title("hello world") == "Hello World"

    def test_apostrophe(self) -> None:
        # string.capwords() does NOT capitalize after apostrophe (unlike str.title())
        assert to_title("they're here") == "They're Here"

    def test_already_title(self) -> None:
        assert to_title("Hello World") == "Hello World"

    def test_all_upper(self) -> None:
        assert to_title("HELLO WORLD") == "Hello World"

    def test_empty(self) -> None:
        assert to_title("") == ""

    def test_multiline(self) -> None:
        assert to_title("hello world\nfoo bar") == "Hello World\nFoo Bar"

    def test_empty_line_preserved(self) -> None:
        assert to_title("hello world\n\nfoo bar") == "Hello World\n\nFoo Bar"

    def test_single_word(self) -> None:
        assert to_title("hello") == "Hello"


class TestToCapitalize:
    def test_basic(self) -> None:
        assert to_capitalize("hello world") == "Hello world"

    def test_all_upper(self) -> None:
        assert to_capitalize("HELLO WORLD") == "Hello world"

    def test_already_capitalized(self) -> None:
        assert to_capitalize("Hello world") == "Hello world"

    def test_empty(self) -> None:
        assert to_capitalize("") == ""

    def test_multiline(self) -> None:
        assert to_capitalize("hello world\nfoo bar") == "Hello world\nFoo bar"

    def test_empty_line_preserved(self) -> None:
        assert to_capitalize("hello world\n\nfoo bar") == "Hello world\n\nFoo bar"

    def test_single_word(self) -> None:
        assert to_capitalize("hello") == "Hello"


class TestToSwapcase:
    def test_basic(self) -> None:
        assert to_swapcase("Hello World") == "hELLO wORLD"

    def test_all_lower(self) -> None:
        assert to_swapcase("hello") == "HELLO"

    def test_all_upper(self) -> None:
        assert to_swapcase("HELLO") == "hello"

    def test_involution(self) -> None:
        assert to_swapcase(to_swapcase("Hello World")) == "Hello World"

    def test_empty(self) -> None:
        assert to_swapcase("") == ""

    def test_multiline(self) -> None:
        assert to_swapcase("Hello\nWorld") == "hELLO\nwORLD"

    def test_empty_line_preserved(self) -> None:
        assert to_swapcase("Hello\n\nWorld") == "hELLO\n\nwORLD"

    def test_numbers_unchanged(self) -> None:
        assert to_swapcase("Hello123") == "hELLO123"
