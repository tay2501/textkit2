"""Every ``--help`` description keeps the line breaks it was written with."""

import argparse
from collections.abc import Iterator

from press.__main__ import make_parser


def _all_parsers(parser: argparse.ArgumentParser) -> Iterator[argparse.ArgumentParser]:
    """Yield *parser* and every subparser below it, each once (aliases share one)."""
    seen: set[int] = set()
    stack = [parser]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        for action in current._actions:
            if isinstance(action, argparse._SubParsersAction):
                stack.extend(action.choices.values())


class TestDescriptionLineBreaks:
    def test_multiline_descriptions_are_not_reflowed(self) -> None:
        # argparse's default HelpFormatter joins a description into one
        # paragraph, so `press stash --help` printed its usage lines run
        # together.  A description written with line breaks needs
        # RawDescriptionHelpFormatter (as daemon and chain use).
        reflowed = [
            p.prog
            for p in _all_parsers(make_parser())
            if p.description
            and "\n" in p.description
            and not issubclass(p.formatter_class, argparse.RawDescriptionHelpFormatter)
        ]
        assert reflowed == []

    def test_stash_help_prints_one_action_per_line(self) -> None:
        parser = next(p for p in _all_parsers(make_parser()) if p.prog == "press stash")
        lines = parser.format_help().splitlines()
        assert any(line.lstrip().startswith("press stash push") for line in lines)
        assert any(line.lstrip().startswith("press stash pop") for line in lines)
