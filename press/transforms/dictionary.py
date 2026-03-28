"""Dictionary-based text replacement transforms (F-08, F-09)."""

from pathlib import Path


def load_tsv(path: Path | str) -> dict[str, str]:
    """Load a TSV dictionary file into a key/value mapping.

    Lines beginning with ``#`` and blank lines are ignored. Only the first
    two tab-separated columns are used; additional columns are ignored.

    Args:
        path: Path to the TSV file (UTF-8, no BOM).

    Returns:
        Dictionary mapping keys to values.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Dictionary file not found: {resolved}")

    table: dict[str, str] = {}
    for line in resolved.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split("\t")
        if len(parts) >= 2:
            table[parts[0]] = parts[1]
    return table


def dict_forward(text: str, table: dict[str, str]) -> str:
    """Apply forward dictionary lookup: replace each line if it matches a key.

    Each line is stripped before lookup. If a stripped line matches a key in
    *table*, the entire line is replaced with the corresponding value. Lines
    that do not match are kept as-is (stripped).

    When *text* contains no newlines the whole string is stripped, looked up,
    and the value (or original stripped text) is returned directly.

    Args:
        text: Input text to transform.
        table: Mapping of keys to replacement values.

    Returns:
        Transformed text with matched lines replaced.
    """
    if not text:
        return text

    if "\n" not in text:
        key = text.strip()
        return table.get(key, key)

    lines = text.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        # Determine the trailing newline sequence (if any)
        if line.endswith("\r\n"):
            ending = "\r\n"
            stripped = line[:-2].strip()
        elif line.endswith(("\n", "\r")):
            ending = line[-1]
            stripped = line[:-1].strip()
        else:
            ending = ""
            stripped = line.strip()

        replacement = table.get(stripped, stripped)
        result.append(replacement + ending)

    return "".join(result)


def dict_reverse(text: str, table: dict[str, str]) -> str:
    """Apply reverse dictionary lookup: swap keys and values, then forward-lookup.

    Builds a reverse mapping ``{value: key}`` from *table* and delegates to
    :func:`dict_forward`.

    Args:
        text: Input text to transform.
        table: Original key→value mapping (values become lookup keys).

    Returns:
        Transformed text with matched lines replaced by their original keys.
    """
    reverse_table = {v: k for k, v in table.items()}
    return dict_forward(text, reverse_table)
