"""Tests for case conversion transforms (F-13 to F-16)."""

from press.transforms.case import to_camel_case, to_kebab_case, to_pascal_case, to_snake_case


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
