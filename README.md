# press

[![Python](https://img.shields.io/badge/python-3.13%20%7C%203.14%20%7C%203.15-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/tay2501/textkit2/actions/workflows/ci.yml/badge.svg)](https://github.com/tay2501/textkit2/actions)

Clipboard text transformer for Windows 11.

> Copy text → run `press <command>` (or a hotkey) → paste the transformed result.

50+ transforms (width, case, line endings, encodings, SQL `IN` lists, JSON, …),
available from the command line and, with the optional daemon, from global
hotkeys in any application.

## Install

Requires Windows 11, Python 3.13+ and [uv](https://docs.astral.sh/uv/) — or no
Python at all with the `press.exe` attached to each
[GitHub Release](https://github.com/tay2501/textkit2/releases) (with `SHA256SUMS.txt`).

```bash
git clone https://github.com/tay2501/textkit2.git
cd textkit2
uv tool install .              # CLI only
uv tool install '.[daemon]'    # CLI + daemon (tray icon, hotkeys)
```

> [!WARNING]
> press is **not on PyPI**. `pip install press` / `uv tool install press` install an unrelated project with the same name.

## Quick start

```bash
press halfwidth -C                   # clipboard "ＴＡＢＬＥ１" → clipboard "TABLE1"
echo "my_variable" | press camel     # → myVariable
press chain trim dedupe lf -C        # several transforms in one pass
press undo                           # put back what the last -C overwrote

press daemon start                   # then: Ctrl+Alt+K, release, type "up" → upper
```

`press --help` lists every command; `press <command> --help` shows its options.

## Highlights

The examples pipe text in with `printf` (Git Bash or another POSIX shell) so
the output is reproducible. In daily use, copy first and drop the pipe: with
no input press reads the clipboard, and `-C` puts the result back. With the
daemon running, a [hotkey](docs/user/hotkeys.md) does the same from any app
(`Ctrl+Alt+K`, release, then the command name).

### Tell NFC from NFD

Text from a Mac often carries `が` as `か` + a combining dakuten (U+3099, NFD).
It looks identical but breaks search and `=` comparisons. `check-norm` (`cn`)
shows which form you have; `nfc` fixes it.

```console
> printf 'が' | press nfd | press check-norm
NFC   no
NFD   yes
NFKC  no
NFKD  yes
> press nfc -C                      # fix the clipboard in place
```

### Swap `_` and `-` (`TABLE_1` ⇔ `TABLE-1`)

```console
> printf 'TABLE_1' | press hyphen      # alias: hy
TABLE-1
> printf 'TABLE-1' | press underscore  # alias: us
TABLE_1
```

### Remove the line breaks Excel adds

Copying a cell from Excel puts a trailing line break on the clipboard, and a
cell with `Alt+Enter` breaks inside it. `strip-newlines` (`nn`) deletes every
line break and inserts nothing in its place.

```console
> press nn -C                          # clipboard in, clipboard out
```

| Copied from one Excel cell (⏎ = line break) | After `press nn -C` |
|---|---|
| `A001⏎` | `A001` |
| `"研究⏎開発"⏎` | `"研究開発"` |

Excel wraps a multi-line cell in `"…"`; press leaves the quotes alone. For a
whole column, use `sql-in` below — `nn` would glue the values together.

### Build a SQL `IN` list

Copy a column of IDs, get a list ready to paste after `WHERE id IN`.

```console
> printf 'A001\nA002\nA003\n' | press sql-in   # alias: sq
'A001','A002','A003'
> printf 'A001\nA002\nA003\n' | press sql-in --wrap
('A001','A002','A003')
> printf 'A001\nA002\n' | press sql-in --quote-char '"'
"A001","A002"
```

From a hotkey, the quote and parentheses come from
[`[sql_in]` in config.toml](docs/user/config.md#sql_in-daemon).

### Change case and naming style

| Command | Alias | Input | Output |
|---|---|---|---|
| `upper` | `up` | `user_name` | `USER_NAME` |
| `lower` | `lo` | `USER_NAME` | `user_name` |
| `camel` | `cm` | `user_name` | `userName` |
| `pascal` | `pc` | `user_name` | `UserName` |
| `snake` | `sn` | `UserName` | `user_name` |
| `kebab` | `kb` | `UserName` | `user-name` |

### Stop other apps overwriting the clipboard (hold)

With the daemon running, `Ctrl+Alt+K` then `h`,`o` makes the clipboard
read-only: copies made by other applications are undone, so you can paste
the same text as often as you need. The tray icon turns red; the same keys
release it. This is a daemon hotkey (ClipboardGuard); the CLI's save/restore
slot is a separate feature — see [CLI](docs/user/cli.md).

```text
Ctrl+Alt+K, then h o     # hold on  (tray icon red)
Ctrl+V … Ctrl+V          # paste as often as you like
Ctrl+Alt+K, then h o     # hold off
```

See [ClipboardGuard](docs/user/daemon.md#clipboardguard-ho) for how it works.

### More

| Command | Input | Output |
|---|---|---|
| `halfwidth` (`hw`) | `ＴＡＢＬＥ＿１` | `TABLE_1` |
| `digits-only` (`dg`) | `¥1,234,567` | `1234567` |
| `markdown-table` (`mdt`) | Excel range (TSV) | Markdown table |
| `chain dedupe sort` | `b` `a` `b` `c` (one per line) | `a` `b` `c` |
| `unix-to-date -u` (`ut`) | `1761436800` | `2025-10-26T00:00:00+00:00` |
| `fix-encoding` (`fe`) | `cafÃ©` (UTF-8 read as Latin-1) | `café` |
| `genpass` (`gp`) | — | a password, kept out of Win+V history |

Everything else — JSON, Base64, URL and HTML escapes, hashes, kana, line
endings, sorting — is in [Transforms](docs/user/transforms.md).

## Muting notifications (screen sharing)

| Action | Hotkey (Ctrl+Alt+K, release, then…) | CLI |
|---|---|---|
| Notifications OFF | `Shift+M`, or `m u` = **mu**te | `press notify off` |
| Notifications ON | `u n m` = **unm**ute | `press notify on` |

Mnemonic: **M**ute ↔ **un-m**ute. Type only `unm` — the command runs there, so
any further keys reach the focused app.

## Diagnosing slow transforms

If a transform takes seconds on a low-spec or EDR-monitored PC, turn on trace
mode to log how long each stage takes. No daemon restart is needed — the
running daemon picks the switch up on the next action.

```bash
press trace on                     # enable trace mode
# reproduce the slow transform (hotkey or `press <command>`)
press daemon logs --level debug    # per-stage timings (elapsed_ms=...)
press trace off                    # disable when done
```

Daemon timings go to `%APPDATA%\press\daemon.log`. Without the daemon,
`press <command>` prints its own breakdown to stderr
(`press: trace read=… delegate=… transform=… write=…`). Clipboard contents are
never logged — only character counts and command names. See
[EDR / slow PCs](docs/user/edr-environments.md#step-4--still-slow-get-a-detailed-trace)
for how to read the timings.

## Documentation

| | |
|---|---|
| [Transforms](docs/user/transforms.md) | Every command, alias and option |
| [CLI](docs/user/cli.md) | Input/output flags, `chain`, `hold`/`undo`, generators |
| [Daemon](docs/user/daemon.md) · [Hotkeys](docs/user/hotkeys.md) | Tray icon, ClipboardGuard, `type`, key bindings |
| [Configuration](docs/user/config.md) · [Dictionary](docs/user/dictionary.md) | `%APPDATA%\press\` files |
| [FAQ](docs/user/faq.md) · [EDR / slow PCs](docs/user/edr-environments.md) | Troubleshooting |
| [Developer guide](docs/dev/index.md) · [Changelog](CHANGELOG.md) | Architecture, contributing, release notes |

## Code signing

Free code signing is provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).
This program will not transfer any information to other networked systems.
See [docs/dev/code-signing.md](docs/dev/code-signing.md) for the full policy (committers, approvers, privacy).

## Support

If press saves you time, you can support it on [Ko-fi](https://ko-fi.com/Z8Z31J3LMW) or [Buy Me a Coffee](https://www.buymeacoffee.com/tay2501).

## License

[MIT](LICENSE)
