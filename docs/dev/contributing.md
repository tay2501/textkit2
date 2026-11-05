# Contributing

## Setup

```bash
git clone https://github.com/tay2501/textkit2.git
cd textkit2
uv sync --all-extras   # plain `uv sync` prunes the daemon extra and daemon tests fail
```

## Run tests

```bash
uv run pytest
uv run pytest --lf          # re-run last failures only
```

## Lint and type check

```bash
uv run ruff format .
uv run ruff check .
uv run mypy press/ --num-workers 4
uv run mypy press/ --platform linux   # CI type-checks on Ubuntu only
```

mypy runs in strict mode plus `truthy-bool`, `redundant-expr` and
`possibly-undefined`. Win32-only function bodies start with
`if sys.platform != "win32": raise OSError(...)` so the Linux lane prunes them;
do not add `# type: ignore` for platform code — it becomes an unused-ignore
error on the other platform.

All of these must pass before opening a pull request.

## Adding a transform

### Simple command (no extra CLI flags)

A "simple" command maps to a pure `fn(text: str) -> str` function with no parameters
beyond the standard I/O flags (`--from-clipboard`, `-C`, `-v`, `-q`, `--fallback`).

1. Add the pure function in `press/transforms/<module>.py`
2. Add one `SimpleCommand(...)` entry to `SIMPLE_COMMANDS` in `press/commands.py`
3. Write tests in `test/unit/test_<module>.py`
4. Document the command in `docs/user/transforms.md`

The CLI subcommand, aliases, help text, daemon hotkey dispatch, and the lazy
export in `press/transforms/__init__.py` are all wired automatically from
`SIMPLE_COMMANDS` — no other files need to change.

### Parametric command (extra CLI flags like `--indent`)

1. Add the pure function in `press/transforms/<module>.py`
2. Add one `ParametricCommand(...)` entry to `PARAMETRIC_COMMANDS` in
   `press/commands.py`, declaring its options as `cli_args=(CliArg(...), ...)`.
   Each `CliArg.kwarg` is forwarded to the transform function as a keyword
   argument. Set `daemon_kwargs` if the daemon should pass config-driven
   arguments during hotkey dispatch.
3. Write tests in `test/unit/test_<module>.py`
4. Document the command in `docs/user/transforms.md`

As with simple commands, everything else (CLI registration, aliases, daemon
dispatch, pipe delegation, lazy exports) derives from the registry entry.

### Rules that apply to every new or renamed command

- **New transforms module** → add a row to `TRANSFORM_CATEGORIES` in
  `press/commands.py` (it decides the `press --help` grouping;
  `test_cli_catalog.py` fails without it).
- **Renamed command or transform keyword** → bump `PROTOCOL_VERSION` in
  `press/_pipe.py`, so a new CLI does not delegate to an older running daemon.
  press has no production users yet: delete the old spelling, do not keep it
  as a deprecated alias.
- **Names and flags** borrow the spelling of the de facto tool for the same
  job (GNU coreutils, grep/ripgrep, jq, Python stdlib). An alias that equals a
  well-known tool's name must mean what that tool does.

### Non-transform command (`clear`, `stash`, `genpass` class)

Add one `SpecialCommand(...)` row to `SPECIAL_COMMANDS` in `press/commands.py`;
argparse aliases and daemon names derive from it (never spell an alias in an
`add_parser` call). A new command group gets its own `press/_cli_<group>.py`
and a row in the `steps` list of `_build_parser()` in `__main__.py`.
`hotkey=True` also requires wiring `CommandDispatcher` in
`press/daemon/_dispatch.py`.

## Commit style

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(transforms): add unicode-escape command
fix(clipboard): handle empty clipboard on hold activation
docs(user): add dictionary reload instructions
```

## Quality gates

Run these in order before every commit:

```bash
uv run ruff format .   # MUST be first — CI fails on "Would reformat"
uv run ruff check .
uv run mypy press/ --num-workers 4
uv run pytest
```

CI (`.github/workflows/ci.yml`) runs the same steps on Ubuntu and Windows ×
Python 3.13 / 3.14 / 3.15; `security.yml` (OSV-Scanner, pip-audit, Bandit,
Semgrep), `codeql.yml` and `dependency-review.yml` gate the build as well.
A pip-audit / OSV failure means a locked dependency has a known CVE — run
`uv lock --upgrade-package <name>`, do not silence the scanner.

Coverage must stay ≥ 76% (`fail_under` in `pyproject.toml`; `pytest-cov` enforces it).

## Building docs

```bash
uv sync --group docs
uv run sphinx-autobuild docs docs/_build/html   # live at http://127.0.0.1:8000
uv run sphinx-build -b html docs docs/_build/html   # static build
```

## Building the Windows executable

```bash
uv sync --group build
uv run pyinstaller --onedir --name press --distpath dist-exe --noconfirm \
  --collect-all press --collect-all jaconv --hidden-import argcomplete \
  press/__main__.py
# → dist-exe/press/press.exe
```

Use `--onedir`, not `--onefile`: `--onefile` re-extracts on every run, while
EDR/antivirus caches the scan of an unpacked directory after the first run.
