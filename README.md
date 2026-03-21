<a href='https://ko-fi.com/Z8Z31J3LMW' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi6.png?v=6' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>
<a href="https://www.buymeacoffee.com/tay2501" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 36px !important;width: 130px !important;" ></a>

# press

[![PyPI](https://img.shields.io/pypi/v/press)](https://pypi.org/project/press/)
[![Python](https://img.shields.io/pypi/pyversions/press)](https://pypi.org/project/press/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/tay2501/textkit2/actions/workflows/ci.yml/badge.svg)](https://github.com/tay2501/textkit2/actions)

Clipboard text transformer with global hotkeys for Windows.

> Copy text → press a hotkey → paste the transformed result.

---

## Install

```bash
uv tool install press
```

## Quick Start

### CLI

```bash
# Full-width → Half-width
echo "ＴＡＢＬＥ１" | press halfwidth          # → TABLE1

# Underscore ↔ Hyphen
echo "USER_ID"      | press hyphen              # → USER-ID
echo "USER-ID"      | press underscore          # → USER_ID

# SQL IN clause
printf "USER1\nUSER2\nUSER3" | press sql-in     # → 'USER1','USER2','USER3'

# Unicode escape ↔ text
echo '\u30c6\u30b9\u30c8' | press unicode-decode  # → テスト
echo "テスト"              | press unicode-encode  # → \u30c6\u30b9\u30c8

# Normalize whitespace / line endings
echo "  USER_ID  "  | press normalize            # → USER_ID
cat file.txt        | press crlf                 # → CRLF unified
```

### Clipboard shortcut (`-c` in, `-C` out)

```bash
press halfwidth   -c -C   # transform clipboard in-place
press sql-in      -c -C
press hold                # protect clipboard from overwrite (toggle)
press clear               # wipe clipboard
```

### Daemon — global hotkeys (always-on)

```bash
press daemon start        # start background daemon

# Default hotkey: Ctrl+Shift+F10, then:
#   W → halfwidth    F → fullwidth    N → normalize
#   S → sql-in       D → dict lookup  E → unicode-decode
#   H → hold toggle  Z → clear

press daemon status
press daemon stop
```

### Custom dictionary (no-pattern replacements)

```bash
# ~/.press/dict/default.tsv
# FOOBER01<TAB>TABLE_HOGEHOGE

press dict add FOOBER01 TABLE_HOGEHOGE
press dict -c -C          # forward lookup from clipboard
press dict -r -c -C       # reverse lookup
```

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
