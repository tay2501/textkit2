# Contributing

## Setup

```bash
git clone https://github.com/your-username/press
cd press
uv sync
```

## Run tests

```bash
uv run pytest
uv run pytest --lf          # re-run last failures only
```

## Lint and type check

```bash
uv run ruff check .
uv run ruff format .
uv run mypy press/
```

All three must pass before opening a pull request.

## Adding a transform

### Simple command (no extra CLI flags)

A "simple" command maps to a pure `fn(text: str) -> str` function with no parameters
beyond the standard I/O flags (`-c`, `-C`, `-v`, `-q`, `--fallback`).

1. Add the pure function in `press/transforms/<module>.py`
2. Add one `SimpleCommand(...)` entry to `SIMPLE_COMMANDS` in `press/commands.py`
3. Add the function to **both** `_LAZY` dict and `TYPE_CHECKING` import block in
   `press/transforms/__init__.py` — **both must be updated or mypy/IDE will break**
4. Write tests in `test/unit/test_<module>.py`
5. Document the command in `docs/user/transforms.md`

The CLI subcommand, aliases, help text, and daemon hotkey dispatch are all wired
automatically from `SIMPLE_COMMANDS` — no other files need to change.

### Parametric command (extra CLI flags like `--indent`)

1. Add the pure function in `press/transforms/<module>.py`
2. Add a `_register_<name>_command()` function in `press/__main__.py`
3. Add a `case "<name>":` branch in `CommandDispatcher._transform()` in `press/daemon.py`
4. Update `_LAZY` and `TYPE_CHECKING` in `press/transforms/__init__.py` (same as above)
5. Write tests in `test/unit/test_<module>.py`
6. Document the command in `docs/user/transforms.md`

## Commit style

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(transforms): add unicode-encode command
fix(clipboard): handle empty clipboard on hold activation
docs(user): add dictionary reload instructions
```

## Quality gates

Run these in order before every commit:

```bash
uv run ruff format .   # MUST be first — CI fails on "Would reformat"
uv run ruff check .
uv run mypy press/
uv run pytest
```

Coverage must stay ≥ 80% (`pytest-cov` enforces this automatically).

## Building docs

```bash
uv sync --extra docs
uv run sphinx-autobuild docs docs/_build/html   # live at http://127.0.0.1:8000
uv run sphinx-build -b html docs docs/_build/html   # static build
```
