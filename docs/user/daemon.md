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

Press `Ctrl+Alt+K` together, release, then type the command name or alias you
would type on the CLI:

```text
Ctrl+Alt+K, then t m      →  trim
Ctrl+Alt+K, then h a l    →  halfwidth
Ctrl+Alt+K, then Shift+D  →  reverse dictionary lookup
Ctrl+Alt+K, then Shift+Z  →  undo the last hotkey transform
```

The command reads the clipboard and writes the result back; paste with `Ctrl+V`.
Resolution rules, editing keys, bindings, and `type`: {doc}`hotkeys`.

## ClipboardGuard (`h`,`o`)

`Ctrl+Alt+K`, then `h`,`o` is a toggle: the first press makes the clipboard
effectively read-only and turns the tray icon red; the same sequence again
releases it. In between, every copy by another application is undone and you
can paste the held text as often as you like — pasting, copying and time
passing never release the guard.

```text
press genpass                 # password → clipboard
Ctrl+Alt+K, then h o        # guard on  (tray icon red)
<switch to the login form>
Ctrl+V                        # paste — the guard stays on
Ctrl+Alt+K, then h o        # guard off (tray icon back to normal)
```

The guard also ends when the daemon exits, and it stands down on its own —
with a tray notification — if another resident tool (a clipboard history
manager, a sync agent) keeps rewriting the clipboard: more than 15 restores in
3 seconds means two tools are fighting, and press gives way rather than loop.

| Layer | Mechanism | Config (`[hold]`) |
|---|---|---|
| 1 | A hidden window watches `WM_CLIPBOARDUPDATE` and restores the held text after any external write (< 1 ms). It writes as the clipboard owner, so its own restores are recognised and not restored again | `monitor_clipboard` |
| 2 | A `WH_KEYBOARD_LL` hook catches `Ctrl+V` / `Shift+Insert` and puts the held text back before the target app reads the clipboard | `intercept_paste_keys` |

Windows has no exclusive clipboard lock, so this is near-absolute rather than
absolute: an application can still read the other copy in the instant before
the restore, and a restore that cannot open the clipboard even after retrying
for ~0.1 s is skipped and recorded in `daemon.log`. It is separate from the
CLI's file-based `press hold` ({doc}`cli`).

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
