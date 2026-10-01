"""CLI registration for the ``config`` command group."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

    from press._cli_helpers import _SubParsers


def _register_config_commands(sub: _SubParsers) -> None:
    """Register the ``config`` subcommand family."""
    config_p = sub.add_parser("config", help="Manage press configuration")
    config_sub = config_p.add_subparsers(dest="config_action", metavar="ACTION")
    # print_help: shown when no ACTION is given (see _handle_config).
    config_p.set_defaults(func=_handle_config, print_help=config_p.print_help)

    val_p = config_sub.add_parser("validate", help="Parse config.toml and report errors")
    _add_file_arg(val_p)

    rst_p = config_sub.add_parser(
        "reset",
        help="Reset config to defaults and create a .toml.bak backup",
    )
    # Spelled out rather than derived from press.config.SECTION_NAMES: this
    # function runs on every press invocation, and importing press.config here
    # would put tomllib and pathlib on the startup path.  The list is pinned to
    # the registry by test_config.TestSectionRegistry instead.
    rst_p.add_argument(
        "--key",
        choices=["hotkeys", "sql_in", "trim", "dictionary", "ui", "hold", "type", "pipelines"],
        default=None,
        metavar="SECTION",
        help=(
            "Section to reset (hotkeys, sql_in, trim, dictionary, ui, hold, type, pipelines); "
            "omit to reset the entire file"
        ),
    )
    _add_file_arg(rst_p)


def _add_file_arg(parser: argparse.ArgumentParser) -> None:
    """Add the ``--file`` option shared by every ``config`` action."""
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

    from press.config import config_reset, config_validate, default_config_path

    raw_file: str | None = getattr(args, "file", None)
    cfg_path = Path(raw_file) if raw_file else default_config_path()

    match action:
        case "validate":
            ok, msg, warnings = config_validate(cfg_path)
            print(f"press config validate: {msg}", file=sys.stdout if ok else sys.stderr)
            for warning in warnings:
                print(f"press config validate: warning: {warning}", file=sys.stderr)
            return 0 if ok else 1
        case "reset":
            key: str | None = getattr(args, "key", None)
            try:
                backed_up = config_reset(cfg_path, key=key)
                if backed_up:
                    print(
                        f"press config reset: backup saved to {cfg_path.with_suffix('.toml.bak')}"
                    )
                section = f" [{key}]" if key else ""
                print(f"press config reset: config{section} reset to defaults → {cfg_path}")
                return 0
            # config_reset handles unreadable/invalid TOML itself, so only
            # the backup copy and the rewrite (file I/O) can fail here.
            except OSError as exc:
                from press._cli_helpers import report_error

                return report_error("config reset", exc)
        case _:
            return 1
