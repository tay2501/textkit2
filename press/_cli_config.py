"""CLI registration for the ``config`` command group."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

    from press._cli_helpers import _SubParsers


def _register_config_commands(sub: _SubParsers) -> None:
    """Register the ``config`` subcommand family."""
    config_p = sub.add_parser("config", help="Manage press configuration")
    config_sub = config_p.add_subparsers(dest="config_action", metavar="ACTION")
    # print_help: shown when no ACTION is given (see _handle_config).
    config_p.set_defaults(func=_handle_config, print_help=config_p.print_help)

    # Each action pins config_action itself: argparse records the name as
    # typed, so an alias would otherwise reach the handler as "ls".
    path_p = config_sub.add_parser("path", help="Print the config file path")
    path_p.set_defaults(config_action="path")

    list_p = config_sub.add_parser(
        "list",
        aliases=["ls"],
        help="Print the effective configuration (defaults + config.toml) as TOML",
    )
    list_p.set_defaults(config_action="list")
    _add_file_arg(list_p)

    val_p = config_sub.add_parser("validate", help="Parse config.toml and report errors")
    val_p.set_defaults(config_action="validate")
    _add_file_arg(val_p)

    rst_p = config_sub.add_parser(
        "reset",
        help="Reset config to defaults and create a .toml.bak backup",
    )
    rst_p.set_defaults(config_action="reset")
    # Spelled out rather than derived from press.config.SECTION_NAMES: this
    # function runs on every press invocation, and importing press.config here
    # would put tomllib and pathlib on the startup path.  The list is pinned to
    # the registry by test_config.TestSectionRegistry instead.
    rst_p.add_argument(
        "--section",
        choices=["hotkeys", "sql_in", "trim", "dictionary", "ui", "hold", "type", "pipelines"],
        default=None,
        metavar="SECTION",
        help=(
            "Section to reset (hotkeys, sql_in, trim, dictionary, ui, hold, type, pipelines); "
            "omit to reset the entire file"
        ),
    )
    rst_p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Do not ask for confirmation (required when stdin is not a terminal)",
    )
    _add_file_arg(rst_p)


def _add_file_arg(parser: argparse.ArgumentParser) -> None:
    """Add the ``--file`` option shared by the file-reading ``config`` actions."""
    parser.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="Config file (default: platform path)",
    )


def _handle_config(args: argparse.Namespace) -> int:
    action: str | None = getattr(args, "config_action", None)
    if action is None:
        args.print_help()
        return 0

    from pathlib import Path

    from press import config

    raw_file: str | None = getattr(args, "file", None)
    cfg_path = Path(raw_file) if raw_file else config.default_config_path()
    # A missing default file means "use the defaults"; a file the user named
    # must exist (git config --file behaves the same way).
    if raw_file and action in ("list", "validate") and not cfg_path.exists():
        print(f"press config {action}: error: file not found: {cfg_path}", file=sys.stderr)
        return 1

    match action:
        case "path":
            print(cfg_path)
            return 0
        case "list":
            try:
                sys.stdout.write(config.config_list(cfg_path))
            except ValueError as exc:
                print(f"press config list: error: {exc}", file=sys.stderr)
                return 1
            return 0
        case "validate":
            ok, msg, warnings = config.config_validate(cfg_path)
            print(f"press config validate: {msg}", file=sys.stdout if ok else sys.stderr)
            for warning in warnings:
                print(f"press config validate: warning: {warning}", file=sys.stderr)
            return 0 if ok else 1
        case "reset":
            return _reset(cfg_path, section=args.section, yes=args.yes)
        case _:
            return 1


def _reset(cfg_path: Path, *, section: str | None, yes: bool) -> int:
    from press.config import config_reset

    target = f"[{section}] in {cfg_path}" if section else str(cfg_path)
    # Nothing to lose when the file does not exist yet, so no question.
    if not yes and cfg_path.exists():
        if not sys.stdin.isatty():
            print(
                "press config reset: error: refusing to reset without confirmation; "
                "pass --yes when stdin is not a terminal",
                file=sys.stderr,
            )
            return 2
        print(f"Reset {target} to defaults? [y/N] ", end="", file=sys.stderr, flush=True)
        try:
            answer = input()
        except (EOFError, KeyboardInterrupt):
            answer = ""
            print(file=sys.stderr)
        if answer.strip().lower() not in ("y", "yes"):
            print("press config reset: aborted", file=sys.stderr)
            return 1

    try:
        backed_up = config_reset(cfg_path, key=section)
    except ValueError as exc:
        print(
            f"press config reset: error: {exc}; run without --section to reset the whole file",
            file=sys.stderr,
        )
        return 1
    # config_reset handles a missing file itself, so only the backup copy and
    # the rewrite (file I/O) can fail here.
    except OSError as exc:
        from press._cli_helpers import report_error

        return report_error("config reset", exc)
    if backed_up:
        print(f"press config reset: backup saved to {cfg_path.with_suffix('.toml.bak')}")
    print(f"press config reset: {target} reset to defaults")
    return 0
