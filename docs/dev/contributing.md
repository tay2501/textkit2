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

1. Add a pure function in `press/transforms/<module>.py`
2. Register it in `press/transforms/__init__.py`
3. Add a CLI subcommand alias in `press/cli.py`
4. Add a default hotkey binding in `press/hotkeys.py`
5. Write tests in `test/test_transforms.py`
6. Document it in `docs/user/transforms.md`

## Commit style

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(transforms): add unicode-encode command
fix(clipboard): handle empty clipboard on hold activation
docs(user): add dictionary reload instructions
```

## Building docs

```bash
uv sync --extra docs
uv run sphinx-autobuild docs docs/_build/html   # live at http://127.0.0.1:8000
uv run sphinx-build -b html docs docs/_build/html   # static build
```
