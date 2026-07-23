# Hotkey Configuration

The `press` daemon registers a **prefix key** system similar to Emacs and nano.

**Two steps:**

1. Press the **prefix chord** simultaneously (default: `Ctrl+Shift+0`)
2. Release all keys, then **type the command name** — the same name or alias
   you would type on the command line

```text
Ctrl+Shift+0   then   t m     →  trim        (press tm)
Ctrl+Shift+0   then   u p     →  upper       (press up)
Ctrl+Shift+0   then   h a l   →  halfwidth
Ctrl+Shift+0   then   h o     →  hold
Ctrl+Shift+0   then   t y     →  type        (see below)
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
Ctrl+Shift+0   then   c l e a n    →  runs the whole pipeline
```

A pipeline cannot shadow a built-in name: if both exist, the command wins.

## `type` — paste by typing instead of by `Ctrl+V`

`Ctrl+Shift+0` then `t`,`y` types the clipboard into the focused window one
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

## Single-key bindings

`[hotkeys.bindings]` still assigns one keystroke to a command, which is faster
than typing a name for the handful you use constantly. Two defaults ship:

| Key after prefix | Command | Why a binding |
|---|---|---|
| `Shift+D` | dict_reverse | reverse lookup has no CLI name to type |
| `Shift+Z` | undo | a panic key deserves a single stroke |

Add your own in `%APPDATA%\press\config.toml`:

```toml
[hotkeys]
prefix = "ctrl+shift+0"   # change the prefix chord

[hotkeys.bindings]
"shift+w" = "halfwidth"   # Ctrl+Shift+0, then Shift+W
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

- Hotkeys do not work when an **elevated (administrator) process** has focus
  (e.g. Task Manager, UAC dialogs). This is a Windows security restriction —
  the same restriction stops `type` from delivering keystrokes there.
- While you are typing a sequence, press **suppresses those keystrokes** so
  they do not leak into the focused window. They are consumed, not delivered:
  if you trigger the prefix by accident, the characters you type before press
  gives up are lost. Press `Esc` to cancel immediately.
- The sequence times out after **2 seconds of inactivity**, and is abandoned
  after **10 seconds** in total regardless of typing.

See {doc}`config` for the full configuration reference.
