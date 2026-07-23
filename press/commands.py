"""Declarative registry of simple and parametric transform commands.

A "simple" command maps 1-to-1 onto a pure transform function that accepts
only ``text: str`` and returns ``str`` — no extra parameters beyond the
standard I/O flags added by ``_add_io_args()``.

A "parametric" command accepts extra CLI arguments.  The daemon dispatches
these with *default* (or config-driven) arguments only, since hotkey bindings
cannot carry per-invocation parameters.  The optional ``daemon_kwargs``
callable extracts config-driven kwargs from ``PressConfig``.

This module is imported by both ``__main__.py`` (CLI registration) and
``daemon.py`` (hotkey dispatch), making it the single source of truth for
all transform commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from press.config import PressConfig


@dataclass(frozen=True, slots=True)
class SimpleCommand:
    """Metadata for one simple (no-extra-args) transform command."""

    name: str
    module: str
    fn: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    help: str = ""


@dataclass(frozen=True, slots=True)
class CliArg:
    """One declarative argparse option for a parametric command.

    ``kwarg`` doubles as the argparse ``dest`` and the keyword-argument name
    passed to the transform function (e.g. flag ``--threshold`` feeds the
    ``confidence_threshold`` parameter of ``fix_encoding``).
    """

    flags: tuple[str, ...]
    kwarg: str
    help: str
    action: str | None = None  # "store_true" for boolean flags; None = value option
    type: Callable[[str], Any] | None = None
    default: Any = None
    metavar: str | None = None

    def __post_init__(self) -> None:
        # Fail fast at import time: argparse actions like "store_true" supply
        # their own default and take no value, so combining them with the
        # value-option fields would be silently ignored during registration.
        if self.action is not None and (
            self.type is not None or self.default is not None or self.metavar is not None
        ):
            raise ValueError(
                f"CliArg {self.flags[0]!r}: action={self.action!r} "
                "cannot be combined with type/default/metavar"
            )


@dataclass(frozen=True, slots=True)
class ParametricCommand:
    """Metadata for one parametric transform command.

    ``cli_args`` declares the extra CLI options registered by ``__main__.py``
    beyond the standard I/O flags.

    ``daemon_kwargs``, when set, is called with the running ``PressConfig``
    to produce the keyword arguments passed to the transform function during
    daemon hotkey dispatch.  ``None`` means call ``fn(text)`` with no extras.
    """

    name: str
    module: str
    fn: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    help: str = ""
    cli_args: tuple[CliArg, ...] = field(default_factory=tuple)
    daemon_kwargs: Callable[[PressConfig], dict[str, Any]] | None = None


# fmt: off
SIMPLE_COMMANDS: tuple[SimpleCommand, ...] = (
    # --- width ---
    SimpleCommand("halfwidth",      "press.transforms.width",      "to_halfwidth",          ("hw",),   "Convert full-width characters to half-width"),
    SimpleCommand("fullwidth",      "press.transforms.width",      "to_fullwidth",          ("fw",),   "Convert half-width characters to full-width"),
    SimpleCommand("enlarge-kana",   "press.transforms.width",      "to_enlarge_smallkana",  ("ek",),   "Expand small kana to normal size (ぁ→あ, ァ→ア)"),
    # --- whitespace ---
    SimpleCommand("normalize",      "press.transforms.whitespace", "normalize_whitespace",  ("norm",), "Normalize whitespace and blank lines"),
    # --- line endings ---
    SimpleCommand("crlf",           "press.transforms.lineending", "to_crlf",               (),        r"Convert line endings to CRLF (\r\n)"),
    SimpleCommand("lf",             "press.transforms.lineending", "to_lf",                 (),        r"Convert line endings to LF (\n)"),
    SimpleCommand("cr",             "press.transforms.lineending", "to_cr",                 (),        r"Convert line endings to CR (\r)"),
    # --- separator ---
    SimpleCommand("underscore",     "press.transforms.separator",  "hyphen_to_underscore",  ("us", "underbar", "ub"), "Convert hyphens to underscores"),
    SimpleCommand("hyphen",         "press.transforms.separator",  "underscore_to_hyphen",  ("hy",),   "Convert underscores to hyphens"),
    SimpleCommand("strip-commas",   "press.transforms.separator",  "strip_commas",          ("sc",),   "Remove commas from text (e.g. 1,234 → 1234)"),
    SimpleCommand("digits-only",    "press.transforms.separator",  "digits_only",           ("dg",),   "Keep only digit characters, removing everything else (e.g. ¥1,234 → 1234)"),
    # --- escape ---
    SimpleCommand("unicode-decode", "press.transforms.escape",     "decode_unicode_escape", ("ud",),   r"Decode \uXXXX escape sequences to text"),
    SimpleCommand("unicode-encode", "press.transforms.escape",     "encode_unicode_escape", ("ue",),   r"Encode text to \uXXXX escape sequences"),
    SimpleCommand("html-decode",    "press.transforms.escape",     "decode_html_entities",  ("hd",),   "Decode HTML entities (e.g. &amp; → &)"),
    SimpleCommand("html-encode",    "press.transforms.escape",     "encode_html_entities",  ("he",),   "Escape HTML special characters (e.g. & → &amp;)"),
    # --- kana ---
    SimpleCommand("katakana",       "press.transforms.kana",       "to_katakana",           ("kata",), "Convert hiragana to katakana (ひらがな → カタカナ)"),
    SimpleCommand("hiragana",       "press.transforms.kana",       "to_hiragana",           ("hira",), "Convert katakana to hiragana (カタカナ → ひらがな)"),
    # --- case ---
    SimpleCommand("snake",          "press.transforms.case",       "to_snake_case",         ("sn",),   "Convert to snake_case"),
    SimpleCommand("camel",          "press.transforms.case",       "to_camel_case",         ("cm",),   "Convert to camelCase"),
    SimpleCommand("pascal",         "press.transforms.case",       "to_pascal_case",        ("pc",),   "Convert to PascalCase"),
    SimpleCommand("kebab",          "press.transforms.case",       "to_kebab_case",         ("kb",),   "Convert to kebab-case"),
    SimpleCommand("upper",          "press.transforms.case",       "to_upper",              ("up",),   "Convert all characters to UPPERCASE"),
    SimpleCommand("lower",          "press.transforms.case",       "to_lower",              ("lo",),   "Convert all characters to lowercase"),
    SimpleCommand("title",          "press.transforms.case",       "to_title",              ("tt",),   "Capitalize the first letter of each word (Title Case)"),
    SimpleCommand("capitalize",     "press.transforms.case",       "to_capitalize",         ("cap",),  "Capitalize the first letter of each line, lowercase rest"),
    SimpleCommand("swapcase",       "press.transforms.case",       "to_swapcase",           ("sw",),   "Swap upper and lower case characters"),
    # --- encode ---
    SimpleCommand("base64-encode",  "press.transforms.encode",     "base64_encode",         ("be",),   "Encode text to Base64"),
    SimpleCommand("base64-decode",  "press.transforms.encode",     "base64_decode",         ("bd",),   "Decode Base64 to text"),
    SimpleCommand("url-encode",     "press.transforms.encode",     "url_encode",            ("urle",), "Percent-encode URL text"),
    SimpleCommand("url-decode",     "press.transforms.encode",     "url_decode",            ("urld",), "Decode percent-encoded URL text"),
    # --- unicode normalization ---
    SimpleCommand("nfc",            "press.transforms.unicode_norm", "to_nfc",              (),        "Normalize to NFC (canonical composition) — Mac→Windows fix"),
    SimpleCommand("nfd",            "press.transforms.unicode_norm", "to_nfd",              (),        "Normalize to NFD (canonical decomposition)"),
    SimpleCommand("nfkc",           "press.transforms.unicode_norm", "to_nfkc",             (),        "Normalize to NFKC (compatibility composition)"),
    SimpleCommand("nfkd",           "press.transforms.unicode_norm", "to_nfkd",             (),        "Normalize to NFKD (compatibility decomposition)"),
    SimpleCommand("check-norm",     "press.transforms.unicode_norm", "check_norm",          ("cn",),   "Report which Unicode normalization forms (NFC/NFD/NFKC/NFKD) the text satisfies"),
    # --- json ---
    SimpleCommand("json-compress",  "press.transforms.json_fmt",   "json_compress",         ("jc",),   "Compress JSON to single line"),
    # --- lines (no-arg) ---
    SimpleCommand("reverse-lines",  "press.transforms.lines",      "reverse_lines",         ("rl",),   "Reverse the order of lines"),
    # --- stats ---
    SimpleCommand("count",          "press.transforms.stats",      "count_text",            ("wc",),   "Count characters, words, lines, and UTF-8 bytes"),
    # --- table ---
    SimpleCommand("markdown-table", "press.transforms.table",      "to_markdown_table",     ("mdt",),  "Convert TSV/CSV to a Markdown table (first row = header)"),
)
# fmt: on

# O(1) lookup by command name or alias — used by daemon.CommandDispatcher._transform()
SIMPLE_COMMAND_INDEX: dict[str, SimpleCommand] = {
    name: cmd for cmd in SIMPLE_COMMANDS for name in (cmd.name, *cmd.aliases)
}


# ---------------------------------------------------------------------------
# Parametric commands (require extra CLI arguments)
# ---------------------------------------------------------------------------


def _sql_in_daemon_kwargs(cfg: PressConfig) -> dict[str, Any]:
    return {"quote_char": cfg.sql_in.quote_char, "wrap": cfg.sql_in.wrap}


def _trim_daemon_kwargs(cfg: PressConfig) -> dict[str, Any]:
    return {"both": cfg.trim.both}


PARAMETRIC_COMMANDS: tuple[ParametricCommand, ...] = (
    ParametricCommand(
        "trim",
        "press.transforms.lines",
        "trim_lines",
        ("tm",),
        "Strip trailing whitespace from each line",
        cli_args=(
            CliArg(
                ("--both", "-b"),
                "both",
                "Strip leading and trailing whitespace (str.strip())",
                action="store_true",
            ),
        ),
        daemon_kwargs=_trim_daemon_kwargs,
    ),
    ParametricCommand(
        "dedupe",
        "press.transforms.lines",
        "dedupe_lines",
        ("dq",),
        "Remove duplicate lines",
        cli_args=(
            CliArg(
                ("--ignore-case", "-i"),
                "ignore_case",
                "Case-insensitive comparison",
                action="store_true",
            ),
            CliArg(
                ("--adjacent", "-a"),
                "adjacent",
                "Remove only adjacent duplicates (like GNU uniq)",
                action="store_true",
            ),
        ),
    ),
    ParametricCommand(
        "sort",
        "press.transforms.lines",
        "sort_lines",
        ("st",),
        "Sort lines",
        cli_args=(
            CliArg(("--reverse", "-r"), "reverse", "Reverse sort order", action="store_true"),
            CliArg(
                ("--numeric", "-n"),
                "numeric",
                "Numeric sort; non-numeric lines go last",
                action="store_true",
            ),
            CliArg(
                ("--ignore-case", "-i"),
                "ignore_case",
                "Case-insensitive sort",
                action="store_true",
            ),
        ),
    ),
    ParametricCommand(
        "sql-in",
        "press.transforms.sql",
        "to_sql_in",
        ("sq",),
        "Convert newline-separated values to SQL IN clause",
        cli_args=(
            CliArg(
                ("--quote-char",),
                "quote_char",
                "Quote character (default: ')",
                default="'",
                metavar="CHAR",
            ),
            CliArg(("--wrap",), "wrap", "Wrap result in parentheses", action="store_true"),
        ),
        daemon_kwargs=_sql_in_daemon_kwargs,
    ),
    ParametricCommand(
        "fix-encoding",
        "press.transforms.encoding_repair",
        "fix_encoding",
        ("fe",),
        "Repair mojibake text by detecting and re-decoding the original encoding (F-15)",
        cli_args=(
            CliArg(
                ("--threshold",),
                "confidence_threshold",
                "Minimum confidence to accept detected encoding (default: 0.7)",
                type=float,
                default=0.7,
                metavar="N",
            ),
        ),
    ),
    ParametricCommand(
        "json-format",
        "press.transforms.json_fmt",
        "json_format",
        ("jf",),
        "Pretty-print JSON",
        cli_args=(
            CliArg(
                ("--indent",),
                "indent",
                "Indentation spaces (default: 2)",
                type=int,
                default=2,
                metavar="N",
            ),
        ),
    ),
    ParametricCommand(
        "hash",
        "press.transforms.hashing",
        "hash_text",
        ("hs",),
        "Compute a hex digest of the text (default: SHA-256)",
        cli_args=(
            CliArg(
                ("--algo", "-a"),
                "algo",
                "Hash algorithm: sha256, sha1, sha512, md5, ... (default: sha256)",
                default="sha256",
                metavar="NAME",
            ),
        ),
    ),
    ParametricCommand(
        "replace",
        "press.transforms.replace",
        "regex_replace",
        ("rp",),
        "Regex (or fixed-string) search & replace",
        cli_args=(
            CliArg(
                ("--pattern", "-p"),
                "pattern",
                "Regex pattern to search (empty = no-op)",
                default="",
                metavar="REGEX",
            ),
            CliArg(
                ("--repl", "-r"),
                "repl",
                r"Replacement text; \1 group refs allowed (default: delete matches)",
                default="",
                metavar="TEXT",
            ),
            CliArg(
                ("--ignore-case", "-i"),
                "ignore_case",
                "Case-insensitive matching",
                action="store_true",
            ),
            CliArg(
                ("--fixed", "-F"),
                "fixed",
                "Treat pattern and replacement as literal strings",
                action="store_true",
            ),
        ),
    ),
    ParametricCommand(
        "number-lines",
        "press.transforms.lines",
        "number_lines",
        ("nl",),
        "Prefix each line with its line number",
        cli_args=(
            CliArg(
                ("--start",),
                "start",
                "First line number (default: 1)",
                type=int,
                default=1,
                metavar="N",
            ),
            CliArg(
                ("--sep",),
                "sep",
                "Separator between number and line (default: TAB)",
                default="\t",
                metavar="SEP",
            ),
        ),
    ),
    ParametricCommand(
        "unix-to-date",
        "press.transforms.timestamp",
        "unix_to_date",
        ("u2d",),
        "Convert Unix time (seconds or ms, per line) to ISO 8601 date",
        cli_args=(
            CliArg(
                ("--utc",),
                "utc",
                "Output in UTC instead of local time",
                action="store_true",
            ),
        ),
    ),
    ParametricCommand(
        "date-to-unix",
        "press.transforms.timestamp",
        "date_to_unix",
        ("d2u",),
        "Convert ISO 8601 date (per line) to Unix time in seconds",
        cli_args=(
            CliArg(
                ("--ms",),
                "ms",
                "Output milliseconds instead of seconds",
                action="store_true",
            ),
        ),
    ),
    ParametricCommand(
        "slug",
        "press.transforms.slug",
        "slugify",
        ("sl",),
        "Convert text to a URL slug (lowercase, hyphens, ASCII-folded)",
        cli_args=(
            CliArg(
                ("--unicode", "-u"),
                "unicode",
                "Keep non-ASCII word characters (e.g. Japanese)",
                action="store_true",
            ),
        ),
    ),
)

# O(1) lookup by name or alias — used by daemon.CommandDispatcher._transform()
PARAMETRIC_COMMAND_INDEX: dict[str, ParametricCommand] = {
    name: cmd for cmd in PARAMETRIC_COMMANDS for name in (cmd.name, *cmd.aliases)
}

# Alias → canonical name — derived from PARAMETRIC_COMMANDS (single source of truth).
# Daemon dispatch resolves these before the registry lookup in CommandDispatcher._transform().
PARAMETRIC_ALIASES: dict[str, str] = {
    alias: cmd.name for cmd in PARAMETRIC_COMMANDS for alias in cmd.aliases
}

# Commands handled inside daemon.CommandDispatcher itself rather than via the
# registries above.  Keep in sync with CommandDispatcher.dispatch() ("clear",
# "hold", "undo") and CommandDispatcher._transform() ("dict", "dict_reverse").
DAEMON_SPECIAL_COMMANDS: frozenset[str] = frozenset(
    {"clear", "hold", "undo", "dict", "dict_reverse"}
)


# ---------------------------------------------------------------------------
# Single source of truth: resolution + execution
#
# Every entry point that turns a command name into a running transform — the
# CLI (``__main__._register_transform_command``), the ``chain`` command
# (``resolve_transform`` below), and the daemon (``CommandDispatcher``) — routes
# through ``resolve_spec`` and ``run_command`` so the module import, the
# alias handling, and the parametric-kwarg precedence live in exactly one place.
# ---------------------------------------------------------------------------


def resolve_spec(command: str) -> SimpleCommand | ParametricCommand | None:
    """Resolve *command* (name or alias) to its registry spec, or ``None``.

    Both indexes already carry alias keys, so a single lookup per registry
    covers names and aliases alike.
    """
    simple = SIMPLE_COMMAND_INDEX.get(command)
    if simple is not None:
        return simple
    return PARAMETRIC_COMMAND_INDEX.get(command)


def is_registry_command(command: str) -> bool:
    """Return whether *command* (name or alias) is a registered transform."""
    return resolve_spec(command) is not None


def run_command(
    command: str,
    text: str,
    *,
    cli_kwargs: dict[str, Any] | None = None,
    config: PressConfig | None = None,
) -> str:
    """Resolve *command* and apply it to *text*, returning the result.

    Parametric options are chosen by precedence:

    1. ``cli_kwargs`` when not ``None`` — explicit per-invocation options from a
       CLI process (or a delegating pipe client).
    2. ``config`` via the command's ``daemon_kwargs`` — the daemon hotkey path,
       where options come from ``config.toml`` rather than the command line.
    3. Otherwise the transform function's own defaults (e.g. a ``chain`` step).

    Raises:
        ValueError: When *command* is not a known transform.
    """
    import importlib

    spec = resolve_spec(command)
    if spec is None:
        raise ValueError(f"unknown command: {command!r}")
    fn = getattr(importlib.import_module(spec.module), spec.fn)
    if isinstance(spec, SimpleCommand):
        return str(fn(text))
    if cli_kwargs is not None:
        kwargs = cli_kwargs
    elif config is not None and spec.daemon_kwargs is not None:
        kwargs = spec.daemon_kwargs(config)
    else:
        kwargs = {}
    return str(fn(text, **kwargs))


def hotkey_sequence_candidates(pipeline_names: Iterable[str] = ()) -> dict[str, str]:
    """Map every hotkey-typeable sequence to its dispatchable command.

    After the prefix chord, the daemon lets the user type a command name or
    alias — the same names the CLI accepts (``press tm`` ⇔ prefix + ``t m``).
    Covers registry commands, the daemon special commands, the CLI-only
    ``cl`` alias for clear, and ``[pipelines]`` names.  Pipeline names never
    override a registry name (same precedence as ``CommandDispatcher``).
    """
    all_commands: tuple[SimpleCommand | ParametricCommand, ...] = (
        *SIMPLE_COMMANDS,
        *PARAMETRIC_COMMANDS,
    )
    candidates: dict[str, str] = {
        name: cmd.name for cmd in all_commands for name in (cmd.name, *cmd.aliases)
    }
    candidates |= {special: special for special in DAEMON_SPECIAL_COMMANDS}
    candidates["cl"] = "clear"
    for name in pipeline_names:
        candidates.setdefault(name, name)
    return candidates


def resolve_transform(command: str) -> Callable[[str], str] | None:
    """Resolve *command* (name or alias) to a ``text -> text`` callable.

    Simple commands map straight onto their transform function.  Parametric
    commands run with their function defaults — per-step options are a CLI
    concern (``press <cmd> --flag``), not a chain-step one.  Backed by
    :func:`run_command` so ``chain`` shares one execution path with the CLI and
    the daemon.

    Returns ``None`` for unknown names so callers can layer their own
    resolution (e.g. ``[pipelines]`` names) on top.
    """
    if resolve_spec(command) is None:
        return None

    def _run(text: str, _cmd: str = command) -> str:
        return run_command(_cmd, text)

    return _run


# ---------------------------------------------------------------------------
# Pipeline helpers (shared by the CLI ``chain`` command, ``config validate``,
# and daemon dispatch so the rules — registry-only steps, no nesting — and
# their wording live in one place).
# ---------------------------------------------------------------------------


def _nesting_error(name: str, step: str) -> str:
    return f"pipeline {name!r}: step {step!r} is a pipeline (nesting is not supported)"


def expand_pipeline_steps(steps: list[str], pipelines: dict[str, tuple[str, ...]]) -> list[str]:
    """Expand ``[pipelines]`` names one level; registry commands pass through.

    Registry commands win a name collision — a pipeline cannot shadow them.

    Raises:
        ValueError: When an expanded step is itself a pipeline name (nesting).
    """
    expanded: list[str] = []
    for step in steps:
        if is_registry_command(step):
            expanded.append(step)
        elif step in pipelines:
            for sub_step in pipelines[step]:
                if sub_step in pipelines:
                    raise ValueError(_nesting_error(step, sub_step))
                expanded.append(sub_step)
        else:
            expanded.append(step)  # unknown — resolve_transform reports it
    return expanded


def validate_pipelines(pipelines: dict[str, tuple[str, ...]]) -> list[str]:
    """Validate ``[pipelines]`` against the command registry.

    Checks (all reported, not just the first): empty step lists, names that
    shadow a registry command or alias, steps that are not registry commands,
    and steps that reference another pipeline (nesting is unsupported).
    """
    errors: list[str] = []
    for name, steps in pipelines.items():
        if is_registry_command(name):
            errors.append(f"pipeline {name!r} shadows a command name — rename it")
        if not steps:
            errors.append(f"pipeline {name!r} has no steps")
        for step in steps:
            if step in pipelines:
                errors.append(_nesting_error(name, step))
            elif not is_registry_command(step):
                errors.append(f"pipeline {name!r}: unknown step {step!r}")
    return errors
