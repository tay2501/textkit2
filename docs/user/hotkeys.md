# Hotkeys

> **Applies to:** daemon only. Start it first: `press daemon start` ({doc}`daemon`).

The daemon uses a **prefix key**, like Emacs or tmux.

**Two steps:**

1. Press the **prefix chord** simultaneously (default: `Ctrl+Alt+K`)
2. Release all keys, then **type the command name** — the same name or alias
   you would type on the command line

```text
Ctrl+Alt+K   then   t m     →  trim        (press tm)
Ctrl+Alt+K   then   u p     →  upper       (press up)
Ctrl+Alt+K   then   h a l   →  halfwidth
Ctrl+Alt+K   then   h o     →  hold
Ctrl+Alt+K   then   t y     →  type        (see below)
```

There is no table of key assignments to memorise: **if the CLI accepts the
name, you can type it after the prefix.** Run `press --help` for the full list.

## How a name is resolved

The daemon dispatches as soon as your keystrokes can only mean one command —
usually after two or three keys, well before the name is complete:

| You type | What happens |
|---|---|
| `t`, `m` | `tm` is trim's alias → runs **trim** |
| `h`, `a`, `l` | only `halfwidth` starts with `hal` → runs **halfwidth** |
| `u`, `p` | `up` is upper's alias, and `upper` is the same command → runs **upper** |
| `c`, `r` | ambiguous: `cr` is a command *and* the start of `crlf` — see below |

```{important}
**Stop typing once it fires.** The moment a command is dispatched, press stops
capturing the keyboard — so any further characters go to the application you
are in. Typing `h`,`o`,`l`,`d` runs hold at `ho` and types `ld` into your
document. Type the name, and let it fire.
```

When what you typed is a complete command name but a longer name also starts
with it (`cr` vs `crlf`), press waits instead of guessing. Finish the longer
name, or confirm the short one:

- press `Enter` to run the short command immediately, or
- simply pause — after the timeout the short command runs.

### Editing keys

| Key | Effect |
|---|---|
| `Enter` | Confirm what you have typed |
| `Backspace` | Delete the last character |
| `Esc` | Cancel silently |

## Pipelines

Any `[pipelines]` name from `config.toml` is typeable exactly like a built-in
command — no binding needed:

```toml
[pipelines]
cleanup = ["trim", "dedupe", "lf"]
```

```text
Ctrl+Alt+K   then   c l e a n    →  runs the whole pipeline
```

A pipeline cannot shadow a built-in name: if both exist, the command wins.

## `type` — paste by typing instead of by `Ctrl+V`

`Ctrl+Alt+K` then `t`,`y` types the clipboard into the focused window one
character at a time. It exists for the case where `Ctrl+V` stalls: a paste
makes the *foreground* application read the clipboard and parse every rich
format on it, so a slow read freezes the window you are looking at. `type`
moves that read into the press daemon and hands the application nothing but
characters.

It is hotkey-only — run from a shell it would type into that shell.

```{warning}
`type` is a keyboard, not a transport. Unlike `Ctrl+V` it is **not atomic and
not lossless**:

- **Newlines are Enter presses.** In a chat client (Slack, Teams) or a search
  box, that *sends*. Set `newline = "unicode"` or `"skip"` in `[type]` if that
  is your usual target.
- Auto-indent, autocomplete, and bracket completion in editors will react to
  the characters as if you had typed them.
- Japanese IME left switched **on** may intercept the input.
- Anything you press while it runs is interleaved; clicking away sends the
  rest to the new window.
- Undo in the target application becomes per-character.
- Emoji and other non-BMP characters travel as surrogate pairs and are
  reassembled by the receiving application — a few do not.

Tabs are safe: press sends `U+0009` as a character rather than `VK_TAB`, so
they insert a tab instead of moving focus.
```

Defaults refuse more than **2000 characters** and send in chunks — a long run
is visible, interruptible, and can overrun a slow application's message queue.
Tune with `[type]` in `config.toml` (see {doc}`config`).

If a modifier key is still held when the command fires, `type` refuses rather
than typing `Ctrl+Enter` where you meant `Enter`. Let go of the prefix chord.

## Commands that are not available from a hotkey

`genpass`, `uuid`, and `chain` are CLI-only:

- **`genpass`** writes with the Windows "sensitive content" marks, which
  deliberately suppress the undo snapshot. A mistyped sequence would replace
  your clipboard with a password and leave no way back.
- **`uuid`** ignores the clipboard rather than transforming it.
- **`chain`** needs a pipeline name as an argument — and pipeline names are
  already typeable directly (see above).

## When a sequence runs nothing

If the keys you typed still fit more than one command when you stop, nothing
runs — `h`,`a` could be `halfwidth` or `hash`. After 2 s (or `Enter`) a
notification says what was possible and how to reach each one:

```text
ha → halfwidth (hal / hw), hash (has / hs)
```

The first sequence continues what you typed; the second is the shortest
overall. A name that matches nothing reads `tq → no command starts with this`.
Both are also written to `daemon.log` (`press daemon logs`), so a missed
notification can be looked up. `Esc`, or a prefix with nothing typed after it,
cancels silently.

## Notifications and screen sharing

Tray notifications show errors only by default (`notify_level = "error"`).
To keep them off a shared screen, switch them off — from the daemon or a
terminal:

```text
Ctrl+Alt+K   then   Shift+M       →  notifications OFF
Ctrl+Alt+K   then   m u           →  notifications OFF (mute)
Ctrl+Alt+K   then   u n m         →  notifications ON  (unmute)

press notify off | on | status
```

Mnemonic: **M**ute ↔ **un-m**ute. `unm` is the shortest prefix of `unmute`
that no other command shares (`u` and `un` also start `undo`, `unicode-…`,
`upper`), so the command runs on `m` — type nothing after it, or the extra
keys reach the focused app.

**Off and on are separate commands, not a toggle**: pressing `Shift+M` again
in a hurry keeps notifications off. Turning them back on shows one
"notifications on" confirmation. The switch takes effect immediately, survives
a daemon restart, and is shared by the CLI and the hotkeys.

press also stays quiet on its own while Windows reports that an application
should not interrupt — a slideshow, a full-screen application, or Windows'
presentation settings. Sharing a window in Teams or Zoom usually does **not**
put Windows in that state, so use the switch before a meeting.

## Single-key bindings

`[hotkeys.bindings]` still assigns one keystroke to a command, which is faster
than typing a name for the handful you use constantly. Three defaults ship:

| Key after prefix | Command | Why a binding |
|---|---|---|
| `Shift+D` | dict_reverse | reverse lookup has no CLI name to type |
| `Shift+M` | notify-off | a screen share can start without warning |
| `Shift+Z` | undo | a panic key deserves a single stroke |

Add your own in `%APPDATA%\press\config.toml`:

```toml
[hotkeys]
prefix = "ctrl+alt+k"     # change the prefix chord

[hotkeys.bindings]
"shift+w" = "halfwidth"   # Ctrl+Alt+K, then Shift+W
"shift+x" = "cleanup"     # a pipeline works too
```

User entries are **merged with** the defaults — specify only what you want to
add or change.

```{warning}
A **single-character** binding fires on the first keypress, which hides every
typed sequence starting with that letter. Binding `k = "trim"` makes `kata`,
`kb`, and every other `k…` name unreachable.

`shift+<key>` chords never collide, because typed sequences are plain
characters. Prefer them. `press config validate` reports any binding that
shadows a sequence:

    press config validate: warning: binding 'k' hides typed sequences kata, katakana, kb, kebab…
```

## Known limitations

- Hotkeys do not work while an **elevated (administrator) window** has focus
  (Task Manager, UAC) — a Windows restriction that also blocks `type` there.
- Keys typed after the prefix are **consumed, not delivered** until a command
  fires. After an accidental prefix, press `Esc`; otherwise the sequence ends
  after **2 s** without a key or **10 s** in total.
- The prefix chord still **reaches the focused application**, so pick one
  that your applications leave unbound. `Ctrl+Alt+Space` is a poor choice:
  Claude Desktop opens its quick-entry box on it, and the VS Code extension
  Continue binds it to "force autocomplete". `Ctrl+Alt+P` opens Sakura
  Editor's page-setup dialog. A Space-based prefix is still accepted
  (`prefix = "ctrl+alt+space"`).
- The default prefix was `Ctrl+Shift+0` before this release. It was changed
  because Windows can claim `Ctrl+Shift+0` as an input-language switch key.
  To keep the old chord, set `prefix = "ctrl+shift+0"` under `[hotkeys]`. A
  `config.toml` written by `press config reset` already contains the old
  value and keeps using it until you edit it.

Configuration keys: {doc}`config`.
