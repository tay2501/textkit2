# CLI Usage

> **Applies to:** CLI only. For hotkeys see {doc}`daemon`.

## Input and output

| Input source | When |
|---|---|
| Positional argument | `press upper "hello"` |
| stdin | piped or redirected (`echo hi \| press upper`), or `-` as the argument |
| Clipboard | run from a terminal with no argument and no pipe, **or** `--from-clipboard` |

Output always goes to **stdout**. `-C` also copies it to the clipboard — and
first saves the text it overwrites, so `press undo` can put it back.

| Flag | Meaning |
|---|---|
| `-C` / `--copy` | Also copy the result to the clipboard (as `pbcopy` / `wl-copy` would) |
| `--from-clipboard` | Read the clipboard even when stdin is not a terminal (scripts, Task Scheduler) |
| `-v` / `--verbose` | Show before/after on stderr |
| `-q` / `--quiet` | No stderr output |
| `--fallback` | On a transform error, print the input unchanged and exit 0 |

Errors print as `press <command>: error: <message>` and exit 1; a usage error
(unknown flag, missing required option) exits 2. Long options must be spelled
out in full — `--trail` is not accepted for `--trailing`.

```{tip}
When the daemon is running, transforms are delegated to it over a named pipe,
which removes interpreter start-up cost on EDR-monitored PCs. Set
`PRESS_NO_DAEMON=1` to force the CLI to transform in-process (troubleshooting).
```

## `chain` — several transforms in one pass

```bash
press chain trim dedupe lf        # left to right; one read, one write
press chain tm lo -C              # aliases work
press chain cleanup               # a [pipelines] name from config.toml
press chain --list                # show configured pipelines
```

Parametric steps run with their defaults (no per-step flags). An unknown or
failing step aborts before anything is written. Pipelines are defined in
{doc}`config`.

## Clipboard tools

| Command | Effect |
|---|---|
| `press clear` (`cl`) | Empty the clipboard |
| `press stash push` / `pop` / `drop` / `list` | Save the clipboard text; restore it later (`pop`), discard it (`drop`), or show whether one is saved (`list`) |
| `press undo` | Swap the clipboard with the text the last `-C` / `clear` / `stash pop` overwrote; run again to redo |

```bash
press stash push     # save what is on the clipboard now
# …copy and paste other things…
press stash pop      # put the saved text back (and delete it)
```

- The stash has one slot, named after `git stash`: `push` fails while a text is
  saved (`pop` or `drop` it first), and `pop` / `drop` fail when nothing is
  saved. `list` prints the length only, never the text.
- `stash.txt` and `undo.txt` live in `%APPDATA%\press\` and are DPAPI-encrypted.
  A stashed `genpass` password comes back still excluded from Win+V history.
- `undo` never snapshots content marked sensitive (a `genpass` password, a
  KeePassXC/Bitwarden copy). `PRESS_NO_UNDO=1` disables the snapshot file.
- A stash is a save/restore slot, not protection. To **block** overwrites until
  you release it, use the daemon's ClipboardGuard ({doc}`daemon`).

## Generators

### `date` / `time` — today's date and the current time

```bash
press date            # 20261106   (default %Y%m%d = YYYYMMDD)
press time            # 211428     (default %H%M%S = hhmmss)
press date +%Y-%m-%d  # 2026-11-06 — one-off format, as in GNU date
press time -u +%H:%M  # 12:14      — UTC
press dt -C           # also copy it to the clipboard (undoable with press undo)
```

Formats are [strftime](https://docs.python.org/3/library/datetime.html#format-codes)
strings, the syntax of GNU `date +FORMAT`: what other tools write as
`YYYY-MM-DD` is `%Y-%m-%d` here. Without `+FORMAT` the format comes from
`[date]` / `[time]` in `config.toml` ({doc}`config`), which is also what the
daemon's hotkey inserts — so `press date` always shows what the shortcut will
paste.

| You want | Format |
|---|---|
| `YYYYMMDD` / `YYYY-MM-DD` / `YYYY/MM/DD` | `%Y%m%d` / `%Y-%m-%d` / `%Y/%m/%d` |
| `2026年11月06日` | `%Y年%m月%d日` |
| `hhmmss` / `hh:mm:ss` / `hh:mm` | `%H%M%S` / `%H:%M:%S` / `%H:%M` |
| ISO 8601 with offset | `%Y-%m-%dT%H:%M:%S%z` |
| No zero padding (`6`, not `06`) | `%#d` on Windows (`%-d` on Linux) |
| A literal `%` | `%%` |

`%a` / `%b` (weekday and month names) are always English, so the CLI and the
daemon agree regardless of the Windows display language. For the time zone use
`%z` (`+0900`): `%Z` prints the Windows display name (`東京 (標準時)` on a
Japanese system), not `JST`.

```{warning}
Inside a **`.bat` / `.cmd` file**, `cmd.exe` treats `%Y%` as a variable and
silently drops it — `press date +%Y%m%d` prints `md`. Double every `%`
(`press date +%%Y%%m%%d`), or leave `+FORMAT` out and set the format in
`config.toml`. The interactive prompt and PowerShell are not affected.
```

### `genpass` / `uuid`

These are CLI-only — a mistyped hotkey must never replace your clipboard with
something that cannot be undone.

```bash
press genpass                  # 20 chars → stdout, and the clipboard on a TTY
press genpass -L 32 -y         # 32 chars with ASCII punctuation
press genpass --no-copy        # never touch the clipboard
press genpass --clear-after 12 # clear after 12 s if the clipboard still holds it
press uuid --count 5 --upper -C  # five uppercase UUID v4s, also to the clipboard
```

`-L/--length` follows `keepassxc-cli generate` and `-y/--symbols` follows
`pwgen` (both add to the character set). `uuid` has no short flags: `uuidgen`
spells the count `-C`, which is `--copy` in press.

`genpass` uses `secrets` and writes with the Windows sensitive-content formats,
so the password stays out of Win+V history and Cloud Clipboard sync.
`--clear-after` only clears if nothing else was copied in the meantime.

## Dictionary

```bash
press dict -C                     # forward lookup of the clipboard, per line
press dict -r -C                  # reverse (value → key)
press dict add FOOBER01 TABLE_X   # list (ls) / add / remove (rm) manage entries
press dict --file ~/my.tsv        # a different TSV file
```

File format and location: {doc}`dictionary`.

## Management commands

| Command | Purpose |
|---|---|
| `press config path` / `list` (`ls`) / `validate` / `reset [--section SECTION] [-y]` | Locate, show, check or restore `config.toml` ({doc}`config`) |
| `press notify off` / `on` / `status` | Mute the daemon's tray notifications, e.g. for screen sharing; `off` is not a toggle ({doc}`hotkeys`) |
| `press trace on` / `off` / `status` | Timing diagnostics ({doc}`edr-environments`) |
| `press daemon …` | Start/stop the daemon ({doc}`daemon`) |
