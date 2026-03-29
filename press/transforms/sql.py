"""SQL IN-clause conversion (F-10)."""


def to_sql_in(text: str, *, quote_char: str = "'", wrap: bool = False) -> str:
    """Convert newline-separated values to a SQL IN-clause value list.

    Each line is stripped and blank lines are removed. Values are quoted
    with ``quote_char`` and joined by commas.

    Args:
        text: Newline-separated values (LF or CRLF).
        quote_char: Quote character to wrap each value. Defaults to ``'``.
        wrap: If True, wrap the entire result in parentheses. Defaults to False.

    Returns:
        Comma-separated quoted values, optionally wrapped in parentheses.

    Raises:
        ValueError: If the input contains no non-blank lines.
    """
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    values = [line for line in lines if line]

    if not values:
        raise ValueError("Input is empty — no values to convert")

    result = ",".join(f"{quote_char}{v}{quote_char}" for v in values)
    return f"({result})" if wrap else result
