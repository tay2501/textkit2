"""Convert TSV/CSV text to a GitHub-flavored Markdown table."""

from __future__ import annotations

import csv
import io


def _format_row(row: list[str], width: int) -> str:
    padded = row + [""] * (width - len(row))
    cells = (cell.replace("|", "\\|").replace("\n", "<br>") for cell in padded)
    return "| " + " | ".join(cells) + " |"


def to_markdown_table(text: str) -> str:
    """Convert TSV or CSV *text* to a Markdown table (first row = header).

    The delimiter is auto-detected: a tab anywhere in the first line selects
    TSV (the format Excel puts on the clipboard), otherwise comma-separated
    parsing with full quote handling via :mod:`csv`.

    Raises:
        ValueError: When the input contains no table rows.
    """
    delimiter = "\t" if "\t" in text.split("\n", 1)[0] else ","
    rows = [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if row]
    if not rows:
        raise ValueError("no table data in input")
    width = max(len(row) for row in rows)
    header, *body = rows
    lines = [
        _format_row(header, width),
        "| " + " | ".join("---" for _ in range(width)) + " |",
        *(_format_row(row, width) for row in body),
    ]
    return "\n".join(lines) + "\n"
