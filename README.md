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

# Case conversion
echo "my_variable" | press camel            # → myVariable
echo "myVariable"  | press snake            # → my_variable
echo "my_variable" | press pascal           # → MyVariable
echo "my_variable" | press kebab            # → my-variable

# Encoding
echo "Hello World" | press base64-encode    # → SGVsbG8gV29ybGQ=
echo "SGVsbG8gV29ybGQ=" | press base64-decode  # → Hello World
echo "a=1&b=2"    | press url-encode       # → a%3D1%26b%3D2

# SQL IN clause
printf "USER1\nUSER2\nUSER3" | press sql-in  # → 'USER1','USER2','USER3'

# JSON
echo '{"b":2,"a":1}' | press json-format   # pretty-print (2-space indent)
cat big.json         | press json-compress  # single line

# Unicode escape ↔ text
echo '\u30c6\u30b9\u30c8' | press unicode-decode  # → テスト
echo "テスト"              | press unicode-encode  # → \u30c6\u30b9\u30c8

# HTML entities
echo '&lt;div&gt;' | press html-decode      # → <div>

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

### Width

| Command | Alias | Description |
|---|---|---|
| `halfwidth` | `hw` | Full-width → half-width (`ＴＡＢＬＥ１` → `TABLE1`) |
| `fullwidth` | `fw` | Half-width → full-width (`TABLE1` → `ＴＡＢＬＥ１`) |

### Whitespace & Line Endings

| Command | Alias | Description |
|---|---|---|
| `normalize` | `norm` | Strip leading/trailing whitespace and blank lines |
| `crlf` | | Unify all line endings to `\r\n` |
| `lf` | | Unify all line endings to `\n` |
| `cr` | | Unify all line endings to `\r` |

### Separators

| Command | Alias | Description |
|---|---|---|
| `hyphen` | `hy` | Underscores → hyphens (`USER_ID` → `USER-ID`) |
| `underscore` | `us` | Hyphens → underscores (`USER-ID` → `USER_ID`) |

### Case Conversion

| Command | Alias | Description |
|---|---|---|
| `snake` | `sn` | Convert to `snake_case` (`myVariable` → `my_variable`) |
| `camel` | `cm` | Convert to `camelCase` (`my_variable` → `myVariable`) |
| `pascal` | `pc` | Convert to `PascalCase` (`my_variable` → `MyVariable`) |
| `kebab` | `kb` | Convert to `kebab-case` (`my_variable` → `my-variable`) |

### Encoding

| Command | Alias | Description |
|---|---|---|
| `base64-encode` | `be` | Encode text to Base64 |
| `base64-decode` | `bd` | Decode Base64 to text |
| `url-encode` | `ue2` | Percent-encode URL text |
| `url-decode` | `ud2` | Decode percent-encoded URL text |

### Escape Sequences

| Command | Alias | Description |
|---|---|---|
| `unicode-decode` | `ud` | Decode `\uXXXX` sequences to text |
| `unicode-encode` | `ue` | Encode text to `\uXXXX` sequences |
| `html-decode` | `hd` | Decode HTML entities (`&amp;` → `&`) |

### SQL & JSON

| Command | Alias | Description |
|---|---|---|
| `sql-in` | `sq` | Newline list → SQL `IN` clause (`'A','B','C'`) |
| `json-format` | `jf` | Pretty-print JSON (default: 2-space indent, `--indent N`) |
| `json-compress` | `jc` | Compress JSON to a single line |

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
uv sync --group docs
uv run sphinx-autobuild docs docs/_build/html   # live preview at http://127.0.0.1:8000
```

---

## Windows Executable

A standalone `press.exe` (no Python required) is attached to each [GitHub Release](https://github.com/tay2501/textkit2/releases).

To build locally:

```bash
uv sync --group build
uv run pyinstaller \
  --onedir --name press --distpath dist-exe --noconfirm \
  --collect-all press --collect-all jaconv \
  --hidden-import argcomplete \
  press/__main__.py
# → dist-exe/press/press.exe
```

> **Note for corporate environments**: Use `--onedir` (not `--onefile`). Antivirus/EDR software caches scans of the unpacked directory after the first run, giving fast startup on subsequent calls.

### PowerShell UTF-8 setup

Add to your PowerShell profile to ensure correct UTF-8 I/O:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
```
