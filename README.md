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

press daemon start                   # then: Ctrl+Shift+0, release, type "up" → upper
```

`press --help` lists every command; `press <command> --help` shows its options.

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
