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

# Case: identifier conversion
echo "my_variable" | press camel            # → myVariable
echo "myVariable"  | press snake            # → my_variable
echo "my_variable" | press pascal           # → MyVariable
echo "my_variable" | press kebab            # → my-variable

# Case: upper / lower / title / capitalize / swapcase
echo "hello world"   | press upper         # → HELLO WORLD
echo "HELLO WORLD"   | press lower         # → hello world
echo "they're here"  | press title         # → They're Here
echo "HELLO WORLD"   | press capitalize    # → Hello world
echo "Hello World"   | press swapcase      # → hELLO wORLD

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
echo 'テスト' | press unicode-decode  # → テスト
echo "テスト"              | press unicode-encode  # → テスト

# HTML entities
echo '&lt;div&gt;' | press html-decode      # → <div>

# Unicode normalization (macOS NFD → Windows NFC, etc.)
echo "café" | press nfc     # → NFC (canonical composition)
echo "café" | press nfkc    # → NFKC (compatibility composition)

# Line operations
printf "banana\napple\ncherry" | press sort         # → apple / banana / cherry
printf "hello   \nworld   "   | press trim          # → strip trailing whitespace
printf "a\nb\na\nc"           | press dedupe        # → a / b / c
printf "10\n2\n1\n20"         | press sort --numeric  # → 1 / 2 / 10 / 20

# Dictionary lookup
press dict add FOOBER01 TABLE_HOGEHOGE --file ~/my.tsv
echo "FOOBER01" | press dict --file ~/my.tsv  # → TABLE_HOGEHOGE
echo "TABLE_HOGEHOGE" | press dict -r --file ~/my.tsv  # → FOOBER01 (reverse)

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
press sort       -c -C
press dedupe --ignore-case -c -C
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

### Line Operations

| Command | Alias | Options | Description |
|---|---|---|---|
| `trim` | `tm` | `--both` | Strip trailing whitespace from each line (`--both` strips leading too) |
| `dedupe` | `dq` | `--ignore-case`, `--adjacent` | Remove duplicate lines, preserving first-occurrence order |
| `sort` | `st` | `--reverse`, `--numeric`, `--ignore-case` | Sort lines (locale-aware; `--numeric` for natural number order) |

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
| `upper` | `up` | Convert to `UPPERCASE` (`hello world` → `HELLO WORLD`) |
| `lower` | `lo` | Convert to `lowercase` (`HELLO WORLD` → `hello world`) |
| `title` | `tt` | Convert to `Title Case` (`they're here` → `They're Here`) |
| `capitalize` | `cap` | Capitalize first letter of each line (`HELLO WORLD` → `Hello world`) |
| `swapcase` | `sw` | Swap upper/lower case (`Hello World` → `hELLO wORLD`) |

### Encoding

| Command | Alias | Description |
|---|---|---|
| `base64-encode` | `be` | Encode text to Base64 |
| `base64-decode` | `bd` | Decode Base64 to text |
| `url-encode` | `urle` | Percent-encode URL text |
| `url-decode` | `urld` | Decode percent-encoded URL text |
| `fix-encoding` | `fe` | Repair mojibake — re-detect and re-decode the original encoding (`--threshold N`) |

### Escape Sequences

| Command | Alias | Description |
|---|---|---|
| `unicode-decode` | `ud` | Decode `\uXXXX` sequences to text |
| `unicode-encode` | `ue` | Encode text to `\uXXXX` sequences |
| `html-decode` | `hd` | Decode HTML entities (`&amp;` → `&`) |

### Unicode Normalization

| Command | Description |
|---|---|
| `nfc` | Canonical composition — precomposed form (Windows/web standard, fixes macOS NFD filenames) |
| `nfd` | Canonical decomposition — base character + combining marks (macOS HFS+ form) |
| `nfkc` | Compatibility composition — collapses full-width, ligatures, etc. |
| `nfkd` | Compatibility decomposition |

### Clipboard Utilities

| Command | Alias | Description |
|---|---|---|
| `clear` | `cl` | Clear the clipboard |
| `hold` | | Toggle clipboard hold — protect contents from overwrite (requires daemon) |

### Dictionary

| Command | Description |
|---|---|
| `press dict [--file PATH] [-r]` | TSV dictionary lookup — exact match per line (`-r` for reverse) |
| `press dict list [--file PATH]` | List all entries in the dictionary file |
| `press dict add KEY VALUE [--file PATH]` | Add an entry to the dictionary |
| `press dict remove KEY [--file PATH]` | Remove an entry from the dictionary |

Default dictionary file: `%APPDATA%\press\dict\default.tsv` (Windows) / `~/.config/press/dict/default.tsv`

TSV format:
```
# comment lines are ignored
FOOBER01	TABLE_HOGEHOGE
USER-ID	USER_ID
```

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

## Daemon & Global Hotkeys

The `press daemon` runs a background process with a system tray icon and global hotkey support. Once started, any clipboard transform is available from any application via a key chord.

```bash
press daemon start    # start tray icon + hotkey listener
press daemon stop     # stop the daemon
press daemon status   # show running / not running
```

### Default key bindings

Prefix: **Ctrl+Shift+F10**, then:

| Key | Command | | Key | Command |
|---|---|---|---|---|
| `w` | halfwidth | | `e` | unicode-decode |
| `f` | fullwidth | | `Shift+E` | unicode-encode |
| `n` | normalize | | `s` | sql-in |
| `c` | crlf | | `d` | dict |
| `l` | lf | | `Shift+D` | dict (reverse) |
| `r` | cr | | `h` | hold (toggle) |
| `u` | hyphen | | `z` | clear clipboard |
| `Shift+U` | underscore | | `k` | trim |
| | | | `o` | dedupe |
| | | | `p` | sort |

### Custom bindings

Create `%APPDATA%\press\config.toml` and add a `[hotkeys.bindings]` section. User-defined entries are **merged with** the defaults — you only need to specify the keys you want to change:

```toml
[hotkeys]
prefix = "ctrl+shift+f10"   # optional — change the leader key

[hotkeys.bindings]
j = "sort"          # add new binding
w = "nfc"           # override existing binding
```

---

## Design Philosophy

press follows a **hybrid CLI design** modeled after [uv](https://docs.astral.sh/uv/) and [ruff](https://docs.astral.sh/ruff/):

- **Transform commands** — short and fast (`press hw`, `px sn`). These are the 90% case.
- **Management commands** — explicit and safe (`press daemon start`). These are rare, low-frequency operations.

All transforms are pure functions with no side effects. I/O is handled exclusively by the CLI layer:

```
stdin / clipboard / positional arg
        ↓
   transform fn(text) → str
        ↓
   stdout + optional clipboard write
```

Error messages follow the format `press <subcommand>: error: <message>` so they are machine-parseable and consistent with tools like git and cargo.

---

## Documentation

| | |
|---|---|
| **User Guide** | [docs/user/](docs/user/index.md) — transforms, hotkeys, dictionary, config |
| **Developer Guide** | [docs/dev/](docs/dev/index.md) — architecture, contributing, API reference |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) |

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
