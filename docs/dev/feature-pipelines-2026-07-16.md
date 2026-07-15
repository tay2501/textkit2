# Feature: Chained Transforms & Named Pipelines (2026-07-16)

Requirements definition → design → official-recommendation review for the
`press chain` command and the `[pipelines]` config section.

---

## 1. Competitive gap analysis

Comparison against the mainstream clipboard/text tools (verified 2026-07):

| Tool | Multi-step transform | User-defined named workflows | Hotkey-bindable workflows | Cost |
|---|---|---|---|---|
| **CopyQ** | ✅ JavaScript-like scripting engine | ✅ Command dialog scripts | ✅ | High (learn a scripting language) |
| **PowerToys Advanced Paste** | ✅ (AI-assisted, per-paste) | ✅ "custom actions" with shortcuts | ✅ | Medium (GUI; AI needs API key/local model) |
| **Espanso** | ➖ (expansion, not transform) | ✅ YAML match files | ✅ (triggers) | Medium (YAML DSL) |
| **Ditto / PasteBar** | ❌ | ❌ | ➖ | — |
| **press (current)** | ➖ shell pipes only (`press trim \| press sort -C`) | ❌ | ❌ (1 hotkey = 1 command) | — |

**Gap**: press has 30+ composable pure transforms, but composing them requires
one process launch *per step* (exactly the startup cost the daemon exists to
avoid on HDD/EDR machines) and a composed workflow cannot be bound to a hotkey.

**Synergy**: the command registry (`commands.py`), TOML config, and daemon
hotkey dispatch already exist — a chained-transform feature reuses all three.

## 2. Requirements

- **R1** `press chain STEP [STEP ...]` applies registered transforms
  left-to-right in a single process with one clipboard/stdin read and one
  write. Aliases resolve (`press chain tm lo` = `trim` → `lower`).
- **R2** Parametric steps run with their function defaults (per-step CLI
  flags are out of scope for v1; the daemon path keeps config-driven kwargs).
- **R3** `[pipelines]` config section defines named step lists, e.g.
  `cleanup = ["trim", "dedupe", "lf"]`; a pipeline name given as a chain STEP
  expands in place. Registry commands always win name collisions.
- **R4** A pipeline name can be bound to a daemon hotkey exactly like a
  command name (`bindings` → `CommandDispatcher.transform`).
- **R5** Fail atomically: any unknown step or failing transform aborts before
  anything is written. Nested pipelines are rejected (no recursion).
- **R6** Discoverability: `press chain --list` prints configured pipelines;
  `press config validate` reports unknown steps, name collisions, nesting,
  and empty pipelines.
- **Non-goals (v1)**: per-step CLI flags, `dict`/`clear`/`hold` as steps,
  pipe-server delegation of whole chains, nested pipelines.

## 3. Design

### 3.1 `press/commands.py`
`resolve_transform(command) -> Callable[[str], str] | None` — resolves a name
or alias through both registries; parametric commands are wrapped to run with
function defaults. Single source of truth reused by `_cli_chain.py`.

### 3.2 `press/_cli_chain.py` (new, per CLAUDE.md CLI-module layout)
- `chain` / `ch` subparser: `steps` positional with `nargs="*"`,
  `--list`, plus the standard I/O flags (`_add_io_args(positional=False)` —
  inline text input is not supported, same as `dict`).
- Handler: expand pipeline names (flat, one level) → resolve every step →
  compose functions → `_run_transform(composed, args)`.
- No pipe delegation: a chain is not a registry command, so `try_delegate`
  is never attempted (each step imports its module locally).

### 3.3 `press/config.py`
- `PressConfig.pipelines: dict[str, tuple[str, ...]]` (default empty).
- `_parse_pipelines()` accepts a TOML table of string arrays.
- `_config_to_toml()` emits the section (with a commented example when empty).
- `config_reset --key pipelines`; `pipeline_errors(config)` helper feeding
  `config_validate` (lazy-imports `press.commands` to keep config import cheap).

### 3.4 `press/daemon/_dispatch.py`
In `CommandDispatcher.transform()`, the unknown-command branch checks
`self._config.pipelines`. Steps are restricted to registry commands
(`ValueError` otherwise) — identical semantics to the CLI and a structural
guarantee against recursion.

## 4. Official-recommendation review

| Design point | Official source | Verdict |
|---|---|---|
| `steps` as `nargs="*"` positional + flags on a subparser | Python docs, argparse `nargs` (verified via Context7, cpython `argparse.rst`; 3.14 fixed intermixed-positional parsing edge cases) | ✅ documented pattern |
| Variadic args for *multiple of the same thing* (transform steps) | clig.dev "Arguments and flags" — args OK when they are the same kind (`rm file1 file2`); flags preferred for *different* things | ✅ conforms |
| `--list` discovery + examples in help epilog | clig.dev "Help" (lead with examples, make discovery easy) | ✅ conforms |
| stdin `-`/pipe composability preserved | clig.dev "Output/composability" | ✅ inherited from `_read_input` |
| `[pipelines]` as TOML table of string arrays | TOML v1.0 spec (arrays of strings in tables); parsed by stdlib `tomllib` like every other section | ✅ conforms |
| Registry-first name resolution, no catch-all abbreviations | clig.dev subcommand guidance (no ambiguous catch-alls) | ✅ conforms |

## 5. Test plan

- `test_chain.py`: CLI subprocess (stdin → chained result), alias resolution,
  unknown step → exit 1 + message, empty steps → exit 2, `--list` (empty and
  populated via patched `load_config`), pipeline expansion, atomic failure.
- `test_config.py`: `[pipelines]` parsing, defaults, round-trip serialization,
  reset `--key pipelines`, `pipeline_errors` (unknown step / collision /
  nesting / empty).
- `test_daemon.py`: dispatcher runs a pipeline, rejects nested pipelines and
  non-registry steps.

## Sources

- PowerToys Advanced Paste: https://learn.microsoft.com/en-us/windows/powertoys/advanced-paste
- CopyQ scripting: https://copyq.readthedocs.io/en/latest/writing-commands-and-adding-functionality.html
- Espanso matches: https://espanso.org/docs/matches/basics/
- Python argparse: https://docs.python.org/3/library/argparse.html
- Command Line Interface Guidelines: https://clig.dev/
