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
uv tool install .                      # CLI transforms only
uv tool install '.[daemon]'            # + daemon / global hotkeys / ClipboardGuard
```

`press` and `px` are both available as command aliases.

For development:

```bash
uv sync                    # CLI transforms only
uv sync --extra daemon     # + daemon / global hotkeys / ClipboardGuard (pystray, pynput)
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

# Strip commas (e.g. numbers copied from the web)
echo "1,234,567"   | press strip-commas      # → 1234567

# Keep digits only (currency symbols, separators, etc. removed)
echo "¥1,234"      | press digits-only       # → 1234
echo "€1.234"      | press digits-only       # → 1234  (comma/period both removed)
echo "１２３円"     | press digits-only       # → １２３ (full-width preserved)

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

# Password generation (cryptographically secure — secrets.choice / os.urandom)
press genpass              # 20-char alphanumeric → stdout + clipboard (TTY)
press genpass -n 32        # 32-char
press genpass -n 16 -s     # 16-char with symbols
press genpass -N           # stdout only, clipboard unchanged
press gp                   # alias

# Dictionary lookup
press dict add FOOBER01 TABLE_HOGEHOGE --file ~/my.tsv
echo "FOOBER01" | press dict --file ~/my.tsv  # → TABLE_HOGEHOGE
echo "TABLE_HOGEHOGE" | press dict -r --file ~/my.tsv  # → FOOBER01 (reverse)

# Normalize whitespace / line endings
echo "  USER_ID  "  | press normalize        # → USER_ID
cat file.txt        | press crlf             # all line endings → CRLF
cat file.txt        | press lf               # all line endings → LF
```

### Daemon & global hotkeys

```bash
uv sync --extra daemon     # install pystray + pynput (first time only)
press daemon start         # start tray icon + hotkey listener

# --- transform from any app via Ctrl+Shift+F10 → key ---
# Copy "ＴＡＢＬＥ＿ＮＡＭＥ", then:
#   Ctrl+Shift+F10 → w   →  paste gives "TABLE_NAME"   (halfwidth)
#   Ctrl+Shift+F10 → n   →  paste gives normalized text (normalize)
#   Ctrl+Shift+F10 → p   →  paste gives sorted lines    (sort)

# --- password + ClipboardGuard ---
press genpass                    # generate password → clipboard
#   Ctrl+Shift+F10 → h           # ClipboardGuard ON  (tray turns red)
#   <navigate to password field in any app>
#   Ctrl+V                       # paste — guard auto-releases

press daemon stop          # stop the daemon
press daemon status        # show running / not running
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
| `enlarge-kana` | `ek` | Expand small kana to normal size (`ぁ` → `あ`, `ァ` → `ア`) |

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
| `strip-commas` | `sc` | Remove commas (`1,234,567` → `1234567`; also strips full-width `，`) |
| `digits-only` | `dg` | Keep only digit characters — removes currency symbols, punctuation, spaces (`¥1,234` → `1234`; `€1.234` → `1234`; `１２３円` → `１２３`) |

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

| Command | Alias | Description |
|---|---|---|
| `nfc` | | Canonical composition — precomposed form (Windows/web standard, fixes macOS NFD filenames) |
| `nfd` | | Canonical decomposition — base character + combining marks (macOS HFS+ form) |
| `nfkc` | | Compatibility composition — collapses full-width, ligatures, etc. |
| `nfkd` | | Compatibility decomposition |
| `check-norm` | `cn` | Report which normalization forms (NFC/NFD/NFKC/NFKD) the text already satisfies |

### Password Generation

```
press genpass [-n N] [-s] [-N] [-C]
```

| Flag | Description |
|---|---|
| `-n N` / `--length N` | Password length (default: **20**) |
| `-s` / `--symbols` | Include ASCII punctuation (`!"#$%&'()*+,...`) |
| `-N` / `--no-clip` | **Print to stdout only — do NOT write to clipboard** (prevents accidental overwrite) |
| `-C` / `--clip-out` | Force clipboard write even in pipe mode |

```bash
press genpass              # 20-char alphanumeric → stdout + clipboard (TTY)
press genpass -n 32        # 32-char alphanumeric
press genpass -n 16 -s     # 16-char with symbols
press genpass -N           # show in terminal only, clipboard unchanged
press gp                   # alias
```

> **TTY auto-clipboard**: when running interactively, the password is written to the clipboard automatically so it is ready to paste immediately. Use `-N` if you only want to view the password without replacing the current clipboard contents.

Uses `secrets.choice()` (backed by `os.urandom()`) — cryptographically secure.

### Clipboard Utilities

| Command | Alias | Description |
|---|---|---|
| `clear` | `cl` | Clear the clipboard |
| `hold` | | Save clipboard text; call again to restore it (see [Clipboard Hold](#clipboard-hold) for real-time protection) |

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

## Clipboard Hold

`press hold` protects clipboard contents from being overwritten. It works in two modes:

### CLI mode (file-based, no daemon required)

```bash
press hold          # saves current clipboard text to disk → prints "press hold: held"
# ... do other copy-paste work ...
press hold          # restores the saved text to the clipboard → prints "press hold: released"
```

First call saves; second call restores. Survives process restarts because the text is written to `%APPDATA%\press\hold.txt`.

### Daemon mode (real-time dual-layer protection)

When the daemon is running, the hotkey **Ctrl+Shift+F10 → `h`** engages **ClipboardGuard** — a two-layer defence that makes the clipboard effectively read-only until you release it:

**Workflow — generate a password and protect it until pasted:**

```
1. press daemon start          # start the daemon (once)
2. press genpass               # generate password → auto-written to clipboard
3. Ctrl+Shift+F10 → h          # engage ClipboardGuard (tray icon turns red)
   ↳ now any app that tries to overwrite the clipboard is blocked
4. Navigate to the password field in any app
5. Ctrl+V                      # paste the password
   ↳ ClipboardGuard auto-releases after the paste (Layer 2)
```

> Use `Ctrl+Shift+F10 → h` again at any time to manually release protection.

| Layer | Mechanism | Reaction time |
|---|---|---|
| **Layer 1** | Hidden Win32 window monitors `WM_CLIPBOARDUPDATE`. Any application that writes to the clipboard triggers an immediate restore. | < 1 ms |
| **Layer 2** | `WH_KEYBOARD_LL` hook intercepts **Ctrl+V / Shift+Insert** *before* the OS dispatches the keystroke, so the protected text is in place before the receiving application reads the clipboard. | 0 ms gap |

The tray icon turns **red** while protection is active. Press the hotkey again (`Ctrl+Shift+F10 → h`) to release.

> **Note:** Windows does not allow a full exclusive clipboard lock (holding `OpenClipboard` open). Layer 1 restores within < 1 ms of any external write; Layer 2 covers the paste path with zero gap. Together they provide near-absolute protection for normal desktop workflows.

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

## Configuration Management

Use `press config` to manage `config.toml` without editing it manually.

### Validate

Check that the config file is syntactically correct and structurally valid:

```bash
press config validate
# press config validate: '%APPDATA%\press\config.toml': valid (schema_version=1)

press config validate --file path/to/config.toml
```

A missing file is not an error — press will use defaults.

### Reset

Restore the config to built-in defaults (creates a `.toml.bak` backup first):

```bash
press config reset           # reset entire file
press config reset --key hotkeys     # reset only [hotkeys] section
press config reset --key sql_in      # reset only [sql_in]
press config reset --key dictionary  # reset only [dictionary]
press config reset --key ui          # reset only [ui]
press config reset --key hold        # reset only [hold]
```

Valid `--key` values: `hotkeys`, `sql_in`, `dictionary`, `ui`, `hold`.

### Config file format

The full config file with all options and defaults (generated by `press config reset`):

```toml
schema_version = 1

[hotkeys]
prefix = "ctrl+shift+f10"

[hotkeys.bindings]
w = "halfwidth"
# ... (see full list in Custom bindings above)

[sql_in]
quote_char = "'"
wrap = false

[dictionary]
files = ["%APPDATA%/press/dict/default.tsv"]

[ui]
startup_notification = true
hold_icon = true
notify_level = "off"   # "off" | "success" | "error" | "all"

[hold]
monitor_clipboard = true       # Layer 1: WM_CLIPBOARDUPDATE watcher
intercept_paste_keys = true    # Layer 2: Ctrl+V / Shift+Insert hook
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
