# CLI Usage

> **Applies to:** CLI only. For hotkeys see {doc}`daemon`.

## Input and output

| Input source | When |
|---|---|
| Positional argument | `press upper "hello"` |
| stdin | piped or redirected (`echo hi \| press upper`), or `-` as the argument |
| Clipboard | `-c`, **or** run from a terminal with no argument and no pipe |

Output always goes to **stdout**. `-C` also writes it to the clipboard — and
first saves the text it overwrites, so `press undo` can put it back.

| Flag | Meaning |
|---|---|
| `-c` / `--clip-in` | Read from the clipboard |
| `-C` / `--clip-out` | Also write the result to the clipboard |
| `-v` / `--verbose` | Show before/after on stderr |
| `-q` / `--quiet` | No stderr output |
| `--fallback` | On a transform error, print the input unchanged and exit 0 |

Errors print as `press <command>: error: <message>` and exit 1.

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
| `press clear` (`cl`) | Empty the clipboard (`--hold` also discards the saved hold file) |
| `press hold` | 1st call: save clipboard text to `hold.txt`. 2nd call: restore it |
| `press undo` | Swap the clipboard with the text the last `-C` / `clear` overwrote; run again to redo |

- `hold.txt` and `undo.txt` live in `%APPDATA%\press\` and are DPAPI-encrypted.
- `undo` never snapshots content marked sensitive (a `genpass` password, a
  KeePassXC/Bitwarden copy). `PRESS_NO_UNDO=1` disables the snapshot file.
- `hold` is a save/restore slot, not protection. To **block** overwrites until
  you paste, use the daemon's ClipboardGuard ({doc}`daemon`).

## Generators

These are CLI-only — a mistyped hotkey must never replace your clipboard with
something that cannot be undone.

```bash
press genpass                  # 20 chars → stdout, and the clipboard on a TTY
press genpass -n 32 -s         # 32 chars with ASCII punctuation
press genpass -N               # never touch the clipboard
press genpass --clear-after 12 # clear after 12 s if the clipboard still holds it
press uuid -n 5 -U -C          # five uppercase UUID v4s, also to the clipboard
```

`genpass` uses `secrets` and writes with the Windows sensitive-content formats,
so the password stays out of Win+V history and Cloud Clipboard sync.
`--clear-after` only clears if nothing else was copied in the meantime.

## Dictionary

```bash
press dict -C                     # forward lookup of the clipboard, per line
press dict -r -C                  # reverse (value → key)
press dict add FOOBER01 TABLE_X   # list / add / remove (rm) manage entries
press dict --file ~/my.tsv        # a different TSV file
```

File format and location: {doc}`dictionary`.

## Management commands

| Command | Purpose |
|---|---|
| `press config validate` / `reset [--key SECTION]` | Check or restore `config.toml` ({doc}`config`) |
| `press trace on` / `off` / `status` | Timing diagnostics ({doc}`edr-environments`) |
| `press daemon …` | Start/stop the daemon ({doc}`daemon`) |
