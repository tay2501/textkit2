"""Line-ending conversion: CRLF / LF / CR (F-04, F-05, F-06).

:func:`to_lf` is the single definition of "what counts as a line ending" for
the whole package — :mod:`press.transforms.lines`,
:mod:`press.transforms.timestamp`, :mod:`press.transforms.sql`,
:mod:`press.transforms.whitespace` and :mod:`press.keystrokes` all route their
normalisation through it rather than spelling the rule out again.
"""


def _normalize_to_lf(text: str) -> str:
    """Internal helper: convert all line endings to LF.

    Two ordered ``str.replace`` calls rather than one regex: CRLF must be
    collapsed before a bare CR is, and the pair measured **6.5-7.5x faster**
    than ``re.sub(r"\\r\\n|\\r|\\n", "\\n", text)`` on mixed and long-line
    inputs (2026-07, CPython 3.13).  ``str.replace`` runs in C without the
    regex engine's per-match bookkeeping, and this is the hottest helper in
    the package — every line-oriented transform starts here.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def to_crlf(text: str) -> str:
    r"""Convert all line endings to CRLF (\r\n)."""
    return _normalize_to_lf(text).replace("\n", "\r\n")


def to_lf(text: str) -> str:
    r"""Convert all line endings to LF (\n)."""
    return _normalize_to_lf(text)


def to_cr(text: str) -> str:
    r"""Convert all line endings to CR (\r)."""
    return _normalize_to_lf(text).replace("\n", "\r")


def strip_newlines(text: str) -> str:
    r"""Remove every line ending, leaving the text on a single line.

    ``\r\n``, ``\r`` and ``\n`` are deleted; **nothing** is inserted in their
    place, so ``"研究\n開発"`` becomes ``"研究開発"`` and ``"hello\nworld"``
    becomes ``"helloworld"``.  Substituting a space between Latin words would
    make the result depend on the script of the surrounding characters — see
    ``docs/dev/design-strip-newlines-2026-07-31.md`` — so the guarantee is
    kept narrow: the output contains no U+000A and no U+000D, and no other
    character is added, removed or moved.  Chain it with ``trim`` or
    ``replace`` when more than that is wanted.

    The trailing newline goes too, unlike in the line-oriented transforms of
    :mod:`press.transforms.lines`, which preserve it.
    """
    return _normalize_to_lf(text).replace("\n", "")
