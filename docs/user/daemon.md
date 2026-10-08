# Daemon Usage

> **Applies to:** daemon only. Install with the `daemon` extra
> (`uv tool install '.[daemon]'`) or use the release `press.exe`.

The daemon adds a tray icon and global hotkeys, so every transform in
{doc}`transforms` works in any application without a terminal.

## Start, stop, status

```bash
press daemon start      # runs in the foreground of this terminal until stopped
press daemon status     # "running" / "not running"; exit 0 / 1 (--json for details)
press daemon stop       # from another terminal — or tray icon → Quit
press daemon restart    # stop, then start (re-reads config.toml)
press daemon logs       # last 50 lines; -f to follow, --level debug, --json
```

Only one daemon runs per user. `config.toml` is read at start-up, so restart
after editing it. The dictionary is re-read on every lookup — no restart
needed after editing a TSV file.

**Start with Windows:** `Win+R` → `shell:startup`, create a shortcut with target
`press daemon start` and set *Run* to **Minimized**.

## Hotkeys

Press `Ctrl+Shift+0` together, release, then type the command name or alias you
would type on the CLI:

```text
Ctrl+Shift+0, then t m      →  trim
Ctrl+Shift+0, then h a l    →  halfwidth
Ctrl+Shift+0, then Shift+D  →  reverse dictionary lookup
Ctrl+Shift+0, then Shift+Z  →  undo the last hotkey transform
```

The command reads the clipboard and writes the result back; paste with `Ctrl+V`.
Resolution rules, editing keys, bindings, and `type`: {doc}`hotkeys`.

## ClipboardGuard (`h`,`o`)

`Ctrl+Shift+0`, then `h`,`o` makes the clipboard effectively read-only until
you paste. The tray icon turns red; repeat the sequence to release early.

```text
press genpass                 # password → clipboard
Ctrl+Shift+0, then h o        # guard on
<switch to the login form>
Ctrl+V                        # paste — the guard releases itself
```

| Layer | Mechanism | Config (`[hold]`) |
|---|---|---|
| 1 | A hidden window watches `WM_CLIPBOARDUPDATE` and restores the held text after any external write (< 1 ms) | `monitor_clipboard` |
| 2 | A `WH_KEYBOARD_LL` hook catches `Ctrl+V` / `Shift+Insert` before the target app reads the clipboard | `intercept_paste_keys` |

Windows has no exclusive clipboard lock, so this is near-absolute rather than
absolute. It is separate from the CLI's file-based `press hold` ({doc}`cli`).

## Undo

Hotkey transforms keep their own in-memory undo slot (`Shift+Z`), separate from
the CLI's `undo.txt`. Sensitive-marked clipboard content is never kept.

## CLI delegation

While the daemon runs, `press <transform>` in a terminal is sent to it over a
per-user named pipe (owner-only ACL, server PID verified). The transform then
runs in the already-warm daemon — the main speed-up on EDR-monitored PCs.
`PRESS_NO_DAEMON=1` turns delegation off.

## Diagnostics

```bash
press trace on                    # takes effect immediately, no restart
# reproduce the slow hotkey or CLI command
press daemon logs --level debug   # elapsed_ms per stage
press trace off
```

The log records command names, character counts, and timings — never clipboard
text. How to read it: {doc}`edr-environments`.

## Limitations

- Hotkeys do not reach an elevated (administrator) window — Task Manager, UAC.
- Keys typed after the prefix are swallowed until a command fires, `Esc` is
  pressed, 2 s pass without a key, or 10 s pass in total.
- `genpass`, `uuid`, and `chain` are CLI-only ({doc}`hotkeys`).
