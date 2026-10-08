<a href='https://ko-fi.com/Z8Z31J3LMW' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi6.png?v=6' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>
<a href="https://www.buymeacoffee.com/tay2501" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 36px !important;width: 130px !important;" ></a>

# press

[![Python](https://img.shields.io/badge/python-3.13%20%7C%203.14-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/tay2501/textkit2/actions/workflows/ci.yml/badge.svg)](https://github.com/tay2501/textkit2/actions)

Clipboard text transformer for Windows 11.

> Copy text → run `press <command>` (or a hotkey) → paste the transformed result.

press has two front ends over the same 50+ transforms:

| | **CLI** | **Daemon** |
|---|---|---|
| How you run it | `press upper` in a terminal | `Ctrl+Shift+0`, then `u`,`p` in any app |
| Needs | nothing extra | the `daemon` extra, `press daemon start` |
| Extras | pipes, `chain`, `genpass`, `uuid` | ClipboardGuard, `type`, tray icon |

---

## Common

### Install

**Requirements:** Windows 11, Python 3.13+, [uv](https://docs.astral.sh/uv/) — or no Python at all with the release `.exe`.

```bash
git clone https://github.com/tay2501/textkit2.git
cd textkit2
uv tool install .              # CLI only
uv tool install '.[daemon]'    # CLI + daemon (pystray, pynput)
```

> [!WARNING]
> press is **not on PyPI**. `pip install press` / `uv tool install press` install an unrelated project with the same name.

A standalone `press.exe` (no Python required) is attached to each [GitHub Release](https://github.com/tay2501/textkit2/releases) with `SHA256SUMS.txt`. `press` and `px` are both available as command names.

### Shared settings and files

Everything lives in `%APPDATA%\press\`. No configuration is required.

| File | Used by | Purpose |
|---|---|---|
| `config.toml` | both | Hotkeys, per-command defaults, pipelines — `press config validate` / `reset` |
| `dict\default.tsv` | both | TSV dictionary for `press dict` / the `Shift+D` hotkey |
| `hold.txt`, `undo.txt` | CLI | `press hold` / `press undo` slots (DPAPI-encrypted) |
| `daemon.log`, `trace` | daemon | Log file; `press trace on` creates the marker |

Details: [config](docs/user/config.md) · [dictionary](docs/user/dictionary.md) · [EDR / slow PCs](docs/user/edr-environments.md) · [FAQ](docs/user/faq.md)

---

## CLI usage

Input is the clipboard when run from a terminal, or stdin when piped. Output goes to stdout; add `-C` to write it back to the clipboard.

```bash
press halfwidth -C                   # clipboard "ＴＡＢＬＥ１" → clipboard "TABLE1"
echo "my_variable" | press camel     # → myVariable
printf "A\nB\nC" | press sql-in      # → 'A','B','C'
press sort --numeric -C              # options per command: press sort --help
press chain trim dedupe lf -C        # several transforms, one read and one write
press undo                           # put back what the last -C overwrote
```

| Flag | Meaning |
|---|---|
| `-c` / `-C` | Read from / write to the clipboard |
| `-v` / `-q` | Before/after on stderr / no stderr |
| `--fallback` | On failure, output the input unchanged (exit 0) |

Clipboard tools: `clear`, `hold` (save, then restore on the second call), `undo` (run again = redo).
Generators: `genpass` (secure password, kept out of Win+V history), `uuid`.

→ **All commands:** [docs/user/transforms.md](docs/user/transforms.md) · CLI-only tools: [docs/user/cli.md](docs/user/cli.md) · or `press --help`

---

## Daemon usage

```bash
press daemon start     # tray icon + hotkeys; keeps running in this terminal
press daemon status    # exit 0 = running (--json for details)
press daemon stop      # from another terminal, or tray → Quit
```

**Hotkeys** — press `Ctrl+Shift+0` together, release, then type the command name or alias you would type on the CLI:

```text
Ctrl+Shift+0, then t m      →  trim
Ctrl+Shift+0, then h a l    →  halfwidth   (fires as soon as only one name matches)
Ctrl+Shift+0, then h o      →  ClipboardGuard on/off
Ctrl+Shift+0, then Shift+Z  →  undo        (default single-key binding)
```

> [!IMPORTANT]
> Stop typing once it fires — later keys go to the focused app (`h`,`o`,`l`,`d` runs hold at `ho` and types `ld`).

- **ClipboardGuard** blocks every clipboard overwrite until your next `Ctrl+V` (tray icon turns red) — e.g. `press genpass`, then `h`,`o`, then paste into a login form.
- **`type`** (`t`,`y`) types the clipboard into the focused window when `Ctrl+V` stalls.
- **Delegation:** while the daemon runs, CLI calls are handed to it over a named pipe, so a CLI transform costs the same on a slow, EDR-monitored PC.

→ **Details:** [docs/user/daemon.md](docs/user/daemon.md) · [docs/user/hotkeys.md](docs/user/hotkeys.md)

---

## Documentation

| | |
|---|---|
| **User Guide** | [docs/user/](docs/user/index.md) — common, CLI, and daemon sections |
| **Developer Guide** | [docs/dev/](docs/dev/index.md) — architecture, contributing, code style, API |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) |

```bash
uv sync --group docs && uv run sphinx-autobuild docs docs/_build/html   # http://127.0.0.1:8000
```

## Windows executable and code signing

Free code signing is provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).
This program will not transfer any information to other networked systems.
See [docs/dev/code-signing.md](docs/dev/code-signing.md) for the full policy (committers, approvers, privacy).

Build locally with `uv sync --group build`, then the PyInstaller command in [docs/dev/contributing.md](docs/dev/contributing.md). Use `--onedir`, not `--onefile` — EDR caches the unpacked directory after the first run.

### PowerShell UTF-8 setup

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
```
