"""``chain`` command group: apply multiple transforms in one invocation.

``press chain trim dedupe lf`` runs the registered transforms left-to-right
with a single input read and a single output write — one process launch
instead of one per step (the startup cost daemon delegation exists to avoid).

Named step lists live in the ``[pipelines]`` section of ``config.toml`` and
expand in place: ``press chain cleanup``.  Registry commands always win a
name collision; nesting (a pipeline referencing a pipeline) is rejected.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from press._cli_helpers import _add_io_args, _run_transform, _SubParsers

if TYPE_CHECKING:
    from collections.abc import Callable


def _expand_steps(steps: list[str]) -> list[str]:
    """Expand ``[pipelines]`` names one level; registry commands pass through.

    The config file is only read when a non-registry step appears, keeping
    the pure-registry fast path free of file I/O.  The expansion itself (and
    its nesting rule) lives in :func:`press.commands.expand_pipeline_steps`.

    Raises:
        ValueError: When an expanded step is itself a pipeline name (nesting).
    """
    from press.commands import expand_pipeline_steps, is_registry_command

    if all(is_registry_command(step) for step in steps):
        return steps

    from press.config import load_config

    return expand_pipeline_steps(steps, load_config().pipelines)


def _resolve_chain(steps: list[str]) -> Callable[[str], str]:
    """Resolve every step upfront so failures happen before any I/O.

    Raises:
        ValueError: When a step is not a registry command or alias.
    """
    from press.commands import resolve_transform

    fns: list[tuple[str, Callable[[str], str]]] = []
    for step in _expand_steps(steps):
        fn = resolve_transform(step)
        if fn is None:
            raise ValueError(f"unknown step {step!r}: not a transform command or [pipelines] name")
        fns.append((step, fn))

    def _composed(text: str) -> str:
        for name, fn in fns:
            try:
                text = fn(text)
            except Exception as exc:
                raise ValueError(f"step {name!r} failed: {exc}") from exc
        return text

    return _composed


def _list_pipelines() -> int:
    """Print configured ``[pipelines]`` entries (name and steps) to stdout."""
    from press.config import load_config

    pipelines = load_config().pipelines
    if not pipelines:
        print("no pipelines defined - add a [pipelines] section to config.toml")
        return 0
    for name, steps in pipelines.items():
        print(f"{name} = {' -> '.join(steps)}")
    return 0


def _register_chain_commands(sub: _SubParsers) -> None:
    p = sub.add_parser(
        "chain",
        aliases=["ch"],
        help="Apply multiple transforms in sequence (one read, one write)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  press chain trim dedupe lf        # three transforms, one pass\n"
            "  press chain tm lo -C              # aliases work; write clipboard\n"
            "  press chain cleanup               # run a [pipelines] entry\n"
            "  press chain --list                # show configured pipelines\n\n"
            "define pipelines in %APPDATA%\\press\\config.toml:\n"
            "  [pipelines]\n"
            '  cleanup = ["trim", "dedupe", "lf"]'
        ),
    )
    p.add_argument(
        "steps",
        nargs="*",
        metavar="STEP",
        help="Transform names/aliases, or a [pipelines] name from config.toml",
    )
    p.add_argument(
        "--list",
        dest="list_pipelines",
        action="store_true",
        help="List pipelines defined in config.toml and exit",
    )
    _add_io_args(p, positional=False)

    def _handler(a: argparse.Namespace) -> int:
        if a.list_pipelines:
            return _list_pipelines()
        if not a.steps:
            print("press chain: error: no steps given (see: press chain --help)", file=sys.stderr)
            return 2
        try:
            composed = _resolve_chain(a.steps)
        except ValueError as exc:
            if not a.quiet:
                print(f"press chain: error: {exc}", file=sys.stderr)
            return 1
        return _run_transform(composed, a)

    p.set_defaults(func=_handler)
