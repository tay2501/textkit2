<a href='https://ko-fi.com/Z8Z31J3LMW' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi6.png?v=6' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>
<a href="https://www.buymeacoffee.com/tay2501" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 36px !important;width: 130px !important;" ></a>

# press

[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/tay2501/textkit2/actions/workflows/ci.yml/badge.svg)](https://github.com/tay2501/textkit2/actions)

Clipboard text transformer for Windows 11.

> Copy text → run `press` → paste the transformed result.

---

## Install

**Requirements:** Python 3.13, [uv](https://docs.astral.sh/uv/)

```bash
# Clone and install as a tool
git clone https://github.com/tay2501/textkit2.git
cd textkit2
uv tool install .
```

`press` and `px` are both available as command aliases.

For development:

```bash
uv sync
uv run press --help
```

---

## Quick Start

### CLI (stdin → stdout)

```bash
# Full-width → Half-width
echo "ＴＡＢＬＥ１" | press halfwidth        # → TABLE1

# Underscore ↔ Hyphen
echo "USER_ID"     | press hyphen            # → USER-ID
echo "USER-ID"     | press underscore        # → USER_ID

# SQL IN clause
printf "USER1\nUSER2\nUSER3" | press sql-in  # → 'USER1','USER2','USER3'

# Unicode escape ↔ text
echo '\u30c6\u30b9\u30c8' | press unicode-decode  # → テスト
echo "テスト"              | press unicode-encode  # → \u30c6\u30b9\u30c8

# Normalize whitespace / line endings
echo "  USER_ID  "  | press normalize        # → USER_ID
cat file.txt        | press crlf             # all line endings → CRLF
cat file.txt        | press lf               # all line endings → LF
```

### Clipboard in-place (`-c` read, `-C` write)

```bash
press halfwidth  -c -C   # transform clipboard in-place
press sql-in     -c -C
press normalize  -c -C
```

---

## Transforms

| Command | Alias | Description |
|---|---|---|
| `halfwidth` | `hw` | Full-width → half-width (`ＴＡＢＬＥ１` → `TABLE1`) |
| `fullwidth` | `fw` | Half-width → full-width (`TABLE1` → `ＴＡＢＬＥ１`) |
| `normalize` | `norm` | Strip leading/trailing whitespace and blank lines |
| `crlf` | | Unify all line endings to `\r\n` |
| `lf` | | Unify all line endings to `\n` |
| `cr` | | Unify all line endings to `\r` |
| `hyphen` | `hy` | Underscores → hyphens (`USER_ID` → `USER-ID`) |
| `underscore` | `us` | Hyphens → underscores (`USER-ID` → `USER_ID`) |
| `sql-in` | `sq` | Newline list → SQL `IN` clause (`'A','B','C'`) |
| `unicode-decode` | `ud` | Decode `\uXXXX` sequences to text |
| `unicode-encode` | `ue` | Encode text to `\uXXXX` sequences |

### Common options

| Flag | Description |
|---|---|
| `-c` / `--clip-in` | Read input from clipboard |
| `-C` / `--clip-out` | Write output to clipboard (also prints to stdout) |
| `-v` / `--verbose` | Show before/after on stderr |
| `-q` / `--quiet` | Suppress all stderr output |
| `--fallback` | Return original text on failure (exit 0) |

---

## Roadmap (Phase 2)

The following features are planned but not yet implemented:

- **Daemon mode** — background process with system tray icon
- **Global hotkeys** — `Ctrl+Shift+F10` → key chord transforms clipboard in any app
- **Clipboard utilities** — `hold` (protect from overwrite), `clear` (wipe)
- **Dictionary lookup** — TSV-based custom string substitution (`dict`)
- **HTML decode** — `&lt;` → `<` (`html-decode`)
- **Encoding repair** — fix mojibake from wrong charset (`fix-encoding`)

---

## Documentation

| | |
|---|---|
| **User Guide** | [docs/user/](docs/user/index.md) — transforms, hotkeys, dictionary, config |
| **Developer Guide** | [docs/dev/](docs/dev/index.md) — architecture, contributing, API reference |
| **Specification** | [SPEC.md](SPEC.md) — full requirements and design decisions |

Build the docs locally:

```bash
uv sync --extra docs
uv run sphinx-autobuild docs docs/_build/html   # live preview at http://127.0.0.1:8000
```
