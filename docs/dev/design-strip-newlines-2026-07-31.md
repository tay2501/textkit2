# Design: `strip-newlines` — remove every line ending (2026-07-31)

Status: **approved** (user decision recorded in §3) — implemented on
`feat/strip-newlines`.

## 1. Goal

One command that turns multi-line clipboard text into a single line by
**removing** its line endings. Paste a wrapped paragraph, a URL broken across
lines by a mail client, or an Excel column, and get one line back.

Contract, stated as narrowly as it can be:

> The output contains no `U+000D` and no `U+000A`. Nothing else changes.

## 2. Specification

| Item | Decision |
|---|---|
| Command | `strip-newlines`, alias `nn` |
| Kind | `SimpleCommand` — no options at all |
| Function | `press.transforms.lineending.strip_newlines(text: str) -> str` |
| Behaviour | `\r\n`, `\r`, `\n` → removed (nothing inserted in their place) |
| Trailing newline | Removed like any other — that is the point of the command |
| Daemon | `Ctrl+Shift+0`, then `n`,`n`; pipe delegation and `chain`/`[pipelines]` support come from the registry |

```python
def strip_newlines(text: str) -> str:
    return _normalize_to_lf(text).replace("\n", "")
```

Routing through `_normalize_to_lf` rather than spelling out
`text.replace("\r", "").replace("\n", "")` keeps
`lineending` the single definition of "what counts as a line ending" for the
package (see `CLAUDE.md`). The extra pass is one C-level `str.replace` over a
clipboard-sized string.

Placement in `lineending.py` — not `lines.py` — follows the same split: the
module owns line *terminators* (`crlf` / `lf` / `cr`), while `lines.py` owns
operations on the *sequence* of lines (sort, dedupe, number). Removing the
terminators belongs to the former.

### Naming

`strip-newlines` says exactly what happens and matches the existing
`strip-commas` (`sc`) — a *remove these characters* command. `join-lines` was
rejected: "join" implies a separator (`str.join`, Vim `J`, `paste -sd`), and
this command inserts none.

### Alias: why not `snl`

`sn` is taken by `snake`, and the obvious extension `snl` **breaks it**. The
leader-key resolver dispatches as soon as every candidate reachable from the
buffer resolves to one command (`SequenceResolver._evaluate`), so today `s`,`n`
fires `snake` instantly — its only continuation is `snake` itself. Adding a
second `sn…` candidate turns that into a *pending* exact match that waits for
the inactivity timeout or Enter. Same trap for `sl`(`slug`) → `sln`, and for
any `s??` alias whose first two characters are an existing alias.

`nn` ("no newlines") is free, and `n` is not itself a candidate, so nothing
that resolves today changes: `n` was already ambiguous (`nfc`, `nl`, `norm`,
`number-lines`, …) and `nn` becomes unique. Verified against
`hotkey_sequence_candidates()` before choosing.

One accepted regression from the *name*: `str` currently resolves uniquely to
`strip-commas`, and with a second `strip-` command it needs `strip-c`. It only
affects users typing the long form of a command that has the two-key alias
`sc`, which is why the naming consistency was judged worth more.

## 3. Rejected alternatives

Researched before the user's decision, recorded so the ground is not
re-covered:

- **Context-aware joining (CSS Text segment-break rules).** W3C CSS Text
  Level 3 §4.1.3 (CR Draft, 2026-06-08) leaves the rule UA-defined and defers
  the CJK specifics to Level 4 §4.3.3; the rule implementations settled on
  (also used by `markdown-it-cjk-breaks`) is: remove the break if either side
  is `U+200B`, or if the East Asian Width of both sides is `F`/`W`/`H` (not
  `A`) and neither side is Hangul — otherwise substitute one space. It is
  implementable in stdlib alone (`unicodedata.east_asian_width`).
  **Rejected**: a command whose output depends on the script of the
  surrounding characters is not predictable from the command name. Users who
  want spaces between English words can pipe through `replace`.
- **`--sep TEXT`** (join with an arbitrary string). Rejected as scope: `press
  replace -p "\n" -r ", "` already does it.
- **`--paragraphs`** (keep blank-line boundaries). Rejected: it contradicts
  the contract in §1 — the output would still contain newlines.
- **A `[join]` config section.** Nothing to configure without the options
  above, and an empty section is a maintenance cost in `_SECTIONS`.

Consequence to document for users: `"hello\nworld"` becomes `"helloworld"`.
That is intended, and `docs/user/transforms.md` says so next to the example.

## 4. Edge cases

| Input | Output | Note |
|---|---|---|
| `""` | `""` | |
| `"hello"` | `"hello"` | no line ending, unchanged |
| `"a\r\nb"` | `"ab"` | CRLF counts as one break, not two |
| `"a\n\n\nb"` | `"ab"` | blank lines vanish with everything else |
| `"a\nb\n"` | `"ab"` | trailing newline removed |
| `"\n\n"` | `""` | |
| `"a\n\rb"` | `"ab"` | LF+CR (reverse order) is two breaks, both removed |
| `"a\u2028b"` | `"a\u2028b"` | U+2028 / U+2029 are **not** line endings here (the package-wide definition, `to_lf`, is CR/LF only) |
| `"a \n b"` | `"a  b"` | surrounding spaces are preserved (no trimming); `trim` exists for that |

## 5. Files touched

| File | Change |
|---|---|
| `press/transforms/lineending.py` | `strip_newlines()` |
| `press/commands.py` | one `SimpleCommand` row |
| `test/unit/test_lineending.py` | `TestStripNewlines` |
| `test/unit/test_sequence.py` | typed-sequence resolution for `nn` |
| `test/unit/test_cli.py` | end-to-end over stdin/stdout, name and alias |
| `README.md`, `docs/user/transforms.md`, `CHANGELOG.md` | documentation |

`docs/user/hotkeys.md` needs no edit: it documents the *resolution rules*, not
a list of commands ("if the CLI accepts the name, you can type it").

CLI registration, daemon dispatch, pipe delegation, `chain` eligibility and
`transforms/__init__._LAZY` are all derived from the registry row — no other
production file changes.

## 6. Test matrix

Every row of §4, plus:

- alias `nn` and name `strip-newlines` both resolve via `resolve_spec`
- `sn` still dispatches `snake` in two keystrokes (the regression the alias
  choice avoids)
- the command is reachable as a typed hotkey sequence (`SequenceResolver`)
- CLI end-to-end: `press strip-newlines` over stdin/stdout
- idempotence: `f(f(x)) == f(x)`
