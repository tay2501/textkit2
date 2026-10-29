# Performance profiling

How to collect performance data for press before changing code to make it
faster — separately for the **CLI** (one short-lived process per call) and
the **daemon** (one long-lived process serving hotkeys and delegated CLI
calls). Measure first, change second, and measure again with the same
procedure: an optimisation without a before/after number is not one.

The user-facing troubleshooting flow for slow PCs is
[Running press under endpoint security agents](../user/edr-environments.md);
this page is the developer counterpart.

## Which tool answers which question

| Question | CLI | Daemon |
|---|---|---|
| Which press stage is slow? | `press trace on` → stderr line | `press trace on` → `daemon.log` `elapsed_ms=` |
| How long does a whole call take? | `hyperfine` | — (hotkeys have no end-to-end timer; use the stage sum) |
| Which import is slow? | `python -X importtime` | `startup.*` labels, then `-X importtime` on `daemon run` |
| How many files does a run open? | audit hook (`test/perf/test_startup.py`) | — |
| Which Python function is slow? | `cProfile` / `profiling.tracing` | sampling profiler attached by PID (`py-spy`, `profiling.sampling`) |
| Is a single transform slow? | `python -m timeit`, `test/perf/test_transforms.py` | same — transforms are shared |
| Is the time outside Python (EDR, disk, clipboard locks)? | Process Monitor, WPR/WPA | Process Monitor, WPR/WPA |

Start at the top of a column and go down only when the row above it points
somewhere you cannot explain.

## Ground rules for every measurement

- **Warm up.** The first run after a change pays for `.pyc` compilation, the
  OS file cache, and the antivirus scan cache. Discard it (hyperfine
  `--warmup`), unless cold start is what you are measuring.
- **Pin the code path.** A running daemon changes what the CLI does: with a
  `press.pid` present the CLI delegates over the named pipe and skips the
  transform import. Measure each path on purpose:
  `$env:PRESS_NO_DAEMON = "1"` forces the in-process path; a started daemon
  gives the delegated path. Point `%APPDATA%` at an empty directory
  (`$env:APPDATA = "$env:TEMP\press-perf"`) to keep leftover `press.pid`,
  `trace`, or `undo.txt` state out of the numbers — the same isolation
  `test/perf/test_startup.py` uses. Do not set `PRESS_NO_DAEMON` or a
  throw-away `%APPDATA%` when profiling the daemon itself — and restore
  `%APPDATA%` before you do (see the session setup below).
- **Pin the input.** A TTY with no argument reads the clipboard, a pipe reads
  stdin, a positional argument reads neither. Use a positional argument
  (`press upper hello`) to keep clipboard and console I/O out of startup
  measurements, and the clipboard only when that is the stage under test.
- **Call the interpreter directly.** `uv run` adds its own startup and a
  project sync check to every call. Use `.venv\Scripts\python.exe -m press`
  (source checkout) or `press.exe` (release build) in timing loops.
- **The dev venv is not the release build.** A source checkout imports
  `site` and runs the venv's `.pth` hooks — the editable install, coverage's
  hook, and with the daemon extra installed `pywin32_bootstrap`, which shows
  up near the top of `-X importtime`; the PyInstaller `--onedir` build does
  not. Decide which one the change is for
  and report numbers for that one.
- **Write the environment down** next to every number: press commit, Python
  version (`python -VV`), build (venv / `press.exe`), daemon on/off, Windows
  build, and which endpoint agents are present (`press daemon status --json`
  → `monitoring_agents`). EDR cost differs per machine by an order of
  magnitude; a number without this context cannot be compared.
- **Never put clipboard contents in a measurement artifact.** press's own
  logs carry only command names and character counts (enforced by
  `TestTimedFieldsWhitelist`). Your measurements must follow the same rule:
  benchmark with literal test strings, not real data — hyperfine's JSON
  export records the full command line, and a profiler's stack or a WPR/ETL
  trace can capture argument values, file paths, and window titles. Raw
  outputs also contain absolute paths with your user name and none of them
  are git-ignored: write them outside the checkout (the examples use
  `$out`, below) and paste only the summary table into the PR.

Session setup used by the CLI examples on this page (PowerShell 7):

```powershell
$out = "$env:TEMP\press-perf\out"; New-Item -ItemType Directory -Force $out | Out-Null
$env:APPDATA = "$env:TEMP\press-perf\appdata"   # no leftover press.pid / trace / undo.txt
$env:PRESS_NO_DAEMON = "1"                       # in-process path
# ... measure ...
# Afterwards — never `Remove-Item Env:APPDATA`, press needs it:
$env:APPDATA = [Environment]::GetFolderPath('ApplicationData')
Remove-Item Env:PRESS_NO_DAEMON
```

## CLI

### 1. Stage breakdown — `press trace on`

The built-in trace splits one transform call into its stages and prints them
to stderr:

```console
$ press trace on
$ press upper hello
HELLO
press: trace read=0.0ms delegate=0.0ms transform=2.6ms write=0.0ms
$ press trace off
```

| Stage | What it covers |
|---|---|
| `read` | `_read_input()` — argument, stdin, or clipboard (including the `press.clipboard`/ctypes import) |
| `delegate` | `try_delegate()` — PID-file stat, and with a daemon the client imports (ctypes, threading, json) and the pipe round trip (connect, server-PID check, request, response) |
| `transform` | in-process `run_command()`, **including the transform module's import** — in a one-shot CLI call that import is usually most of it; **absent** when delegation succeeded — the daemon logs that time as `transform.run` instead |
| `write` | stdout; with `-C` also the undo snapshot (clipboard read, DPAPI encryption, file write) and the clipboard write |

Each stage includes the lazy imports it triggers. What it does **not**
cover: interpreter startup, the eager imports, and argparse — everything
before the handler runs, which is usually the largest part of a CLI call on
a monitored PC. Use hyperfine for the total and `-X importtime` for the
import share. `-q` suppresses the line (it promises
no stderr), and the marker is the same file the daemon reads, so the daemon
logs at DEBUG while it exists.

### 2. End-to-end wall clock — hyperfine

[hyperfine](https://github.com/sharkdp/hyperfine) (`winget install hyperfine`)
is the de facto tool for timing a whole command: warm-up runs, repeated
measurement, mean/σ/min/max, and comparison of several commands in one table.

```powershell
# after the session setup above
hyperfine -N --warmup 3 --runs 30 `
  --export-markdown "$out\cli-local.md" `
  ".venv/Scripts/python.exe -m press upper hello" `
  ".venv/Scripts/python.exe -m press --version"
```

- **Use forward slashes in the command string.** hyperfine splits it with
  POSIX shell-word rules, where an unquoted `\` escapes the next character —
  `.venv\Scripts\python.exe` becomes `.venvScriptspython.exe` and is not
  found. Windows accepts `/` in the path.
- `-N` (`--shell=none`) runs the command without a shell, so no shell
  start-up is mixed into the number; it is the default since hyperfine 2.0.0
  and harmless to spell out for older versions. It also means no shell
  syntax: set environment variables in the PowerShell session beforehand
  (the child inherits them) or with hyperfine 2.0's `--env`.
- `--prepare "<cmd>"` runs before *each* measured run, for cold-cache
  experiments. It always goes through a shell (`cmd.exe` on Windows), even
  with `-N`.
- To compare delegated vs. in-process, the second table needs a daemon that
  the CLI really reaches: stop your everyday daemon first (the singleton
  mutex is per user, not per `%APPDATA%`, so a running one makes a new start
  report "already running" and nothing is delegated), start one from the
  same checkout (`Remove-Item Env:PRESS_NO_DAEMON;
  .venv\Scripts\python.exe -m press daemon start` — a `press` on `PATH` may be
  an older build whose pipe name embeds a different `PROTOCOL_VERSION`, and
  the CLI then silently falls back to in-process), and confirm with
  `press trace on` that `transform=` is gone from the trace line.
- Without hyperfine, `Measure-Command { .venv\Scripts\python.exe -m press upper hello }`
  gives a single sample — repeat it and discard the first.

`test/perf/test_startup.py::TestStartupWallTime` is the CI guard for this
number (`press --version` ≤ 2.0 s after one warm-up).

### 3. Import time — `-X importtime`

CPython's built-in import profiler prints one line per imported module with
self and cumulative time in microseconds, to stderr:

```powershell
.venv\Scripts\python.exe -X importtime -m press upper hello 2> "$out\importtime.txt"
```

Top modules by cumulative time:

```powershell
Get-Content "$out\importtime.txt" |
  Select-String '^import time:\s+(\d+) \|\s+(\d+) \|(\s*)(.+)$' |
  ForEach-Object {
    $g = $_.Matches[0].Groups
    [pscustomobject]@{ self_us = [int]$g[1].Value; cumulative_us = [int]$g[2].Value; module = $g[4].Value }
  } |
  Sort-Object cumulative_us -Descending | Select-Object -First 15
```

- The indentation of the module column is the import nesting; read the file
  itself when you need to know *who* imported a module.
- Python 3.14+ also accepts `-X importtime=2`, which adds `cached` lines for
  modules that were already loaded — useful to see that a lazy import is
  re-requested but free. The parser above skips those lines.
- `PYTHONPROFILEIMPORTTIME=1` (or `2`) is the environment-variable form.
  It does not reach a PyInstaller build: the frozen interpreter ignores
  `PYTHON*` variables. Profile imports from a source checkout running the
  same Python version as the release; if the frozen build itself is in
  question, PyInstaller passes `X` options other than `utf8`/`dev` on to the
  interpreter, so a diagnostic build with `('X importtime', None, 'OPTION')`
  in the spec's `options` should work (not tried in this project).
- The output can be garbled in multi-threaded programs (CPython docs); the
  CLI is single-threaded, the daemon is not — see the daemon section.

### 4. File-open count — audit hook

On EDR-monitored PCs every file open is a scan, so the *number* of opens
matters more than their duration on a developer machine.
`test/perf/test_startup.py` counts them with a `sys.addaudithook` hook on the
`open` event and enforces `_MAX_TRANSFORM_FILE_OPENS`:

```console
uv run pytest test/perf/test_startup.py -k file_open -q
```

To see *which* files are opened, run the same idea by hand, printing the
path instead of counting it:

```powershell
.venv\Scripts\python.exe -c "import sys; sys.addaudithook(lambda e, a: e == 'open' and print('open', a[0], file=sys.stderr)); sys.argv = ['press', 'upper', 'hello']; import runpy; runpy.run_module('press.__main__', run_name='__main__')" 2> "$out\opens.txt"
```

For what the endpoint agent actually does with those opens, see
Process Monitor in [Outside Python](#outside-python--process-monitor-and-wpr) below.

### 5. Function level — `cProfile` / `profiling.tracing`

A deterministic profiler records every call; good for "which function
inside this 30 ms transform", poor for anything shorter than its own
overhead.

```powershell
.venv\Scripts\python.exe -m cProfile -o "$out\cli.pstats" -m press upper hello
.venv\Scripts\python.exe -m pstats "$out\cli.pstats"   # then: sort cumulative / stats 20
```

On Python 3.15 `cProfile` is an alias of the new `profiling.tracing` module
and stays supported; the pure-Python `profile` module is deprecated (removal
in 3.17) — do not use it.

Python 3.15 also ships a statistical profiler, `profiling.sampling`, that
adds almost no overhead to the target. A CLI call is short, so raise the
sampling rate from the default 1 kHz:

```powershell
.venv\Scripts\python.exe -m profiling.sampling run -r 20khz --flamegraph -o "$out\cli.html" -m press upper hello
```

It requires Python 3.15+ (the profiler and the target must be the same minor
version). On 3.13/3.14 use `cProfile`, or `py-spy record -- python -m press …`.

### 6. A single transform — `timeit` and `test/perf`

When the stage breakdown points at `transform`, take process startup out
entirely:

```console
.venv\Scripts\python.exe -m timeit -s "from press.commands import run_command; t = 'hello world ' * 1000" "run_command('upper', t)"
```

`test/perf/test_transforms.py` runs every registered command on 10 KB of
valid input against a 50 ms budget; a new command is covered automatically.
Run it before and after a transform change:

```console
uv run pytest test/perf/test_transforms.py -q
```

## Daemon

Run the daemon examples with the real `%APPDATA%` and without
`PRESS_NO_DAEMON` (restore them as shown in the session setup); `$out` is the
same output directory.

### 1. Stage timings — `press trace on` + `daemon.log`

The daemon wraps each stage in `press.daemon._logs.timed()`, which writes a
DEBUG line with `elapsed_ms=` only while the trace marker exists. The marker
is re-read once per dispatched hotkey action and once per pipe request, so
toggling it needs no restart — but `hotkey.wait_stopped` and `pipe.serve` are
entered just *before* that re-read, so the first action after `press trace on`
lacks those two lines and the first one after `press trace off` still writes
them. Discard the first repetition.

```console
$ press trace on
# reproduce: the hotkey, or `press <command>` with the daemon running
$ press daemon logs --level debug -n 200
2026-10-29T10:15:03 DEBUG    hotkey.wait_stopped elapsed_ms=812.40
2026-10-29T10:15:03 DEBUG    clipboard.get elapsed_ms=2.10
2026-10-29T10:15:03 DEBUG    transform.run elapsed_ms=0.85 cmd=upper chars=340
2026-10-29T10:15:03 DEBUG    clipboard.set elapsed_ms=2.01
$ press trace off
```

| Label | Path | Covers |
|---|---|---|
| `startup.config_load` | start | `load_config()` |
| `startup.hotkeys_init` | start | `HotkeyManager` construction (hotkey-sequence table only; pynput is imported later, untimed, when the tray starts the listeners) |
| `startup.pipe_server_start` | start | named-pipe server thread start |
| `startup.tray_init` | start | tray icon image creation, including the Pillow import |
| `hotkey.wait_stopped` | hotkey | joining the leader-key listener before dispatch |
| `clipboard.get` / `clipboard.set` | hotkey | Win32 clipboard read / write of a transform, `dict`, or pipeline |
| `transform.run` | hotkey, pipe | `run_command()` of a registry command, including a first-use module import (`cmd=`, `chars=`); a pipeline logs one per step |
| `keystrokes.type` | hotkey `type` | `SendInput` typing (`chars=`); the clipboard read before it is not timed |
| `pipe.transform` | pipe | `dispatcher.transform()` after the request is validated — contains `transform.run` |
| `pipe.serve` | pipe | whole request: read, handle, write, flush, disconnect — contains `pipe.transform` |

Reading it correctly:

- **Labels nest**, they do not add up: `pipe.serve` ⊇ `pipe.transform` ⊇
  `transform.run`. `pipe.serve − pipe.transform` is pipe I/O and validation; the CLI's
  `delegate=` minus `pipe.serve` is the client side (imports, connect,
  server-PID check) plus the server's accept and thread start.
- **There is no end-to-end hotkey timer.** The time from the prefix key to
  `hotkey.wait_stopped` (typing the sequence, the leader timeout) is not
  logged, and timestamps have one-second resolution, so gaps between lines
  cannot be measured from the log. The undo snapshot (`_remember_for_undo`)
  and the success notification also run untimed between and after the
  labelled blocks. The sum of the labels is therefore a lower bound of the
  daemon's share.
- **`startup.*` lines appear only if the marker existed when the daemon
  started** — the level is set once in `_setup_logging()` before them. For
  startup timings: `press daemon stop`, `press trace on`, `press daemon start`.
  `press daemon start` itself waits for the PID file, so
  `Measure-Command { press daemon start }` is the user-visible startup
  total (to 0.1 s: `start` polls for the PID file every 100 ms). The pystray and pynput imports and the listener start happen after
  the last `startup.*` label and are not timed individually; that
  difference is what `-X importtime` on a foreground `daemon run` (below)
  breaks down.
- `clear`, `hold`, `undo`, and `notify-off`/`notify-on` have no stage
  labels; profile them with a sampling profiler.
- `daemon.log` rotates at 5 MB × 3 backups; `-n all` reads the current file
  only.

Aggregate many runs (repeat the hotkey 20–30 times, then):

```powershell
press daemon logs --level debug --json -n all |
  ConvertFrom-Json |
  ForEach-Object { if ($_.msg -match '^(\S+) elapsed_ms=([\d.]+)') { [pscustomobject]@{ label = $Matches[1]; ms = [double]$Matches[2] } } } |
  Group-Object label |
  ForEach-Object {
    $ms = @($_.Group.ms | Sort-Object)
    [pscustomobject]@{ label = $_.Name; n = $ms.Count; median_ms = $ms[[int][math]::Floor(($ms.Count - 1) / 2)]; max_ms = $ms[-1] }
  } |
  Sort-Object max_ms -Descending | Format-Table -AutoSize
```

(`median_ms` is the lower median for an even count.) It pools every
`cmd=`, both paths, and whatever older sessions are still in the file — for a
clean sample, note the time before you start or group by `cmd=` as well. Report median and max:
a hotkey that is usually fast but sometimes stalls is the typical EDR
signature, and the mean hides it.

**Adding a new timing point:** wrap the stage in `with timed("area.stage", …)`
and pass only `len(...)`, literals, or `cmd`/`command` as fields —
`TestTimedFieldsWhitelist` fails CI otherwise. Add the label to the table
above.

### 2. Python stacks of the running daemon — sampling profilers

When a stage is slow and you need to know *where in Python*, attach a
sampling profiler to the live daemon by PID. Sampling reads the target's
memory from outside, so the daemon runs unmodified and at full speed.

The PID is in `%APPDATA%\press\press.pid` and in `press daemon status --json`
(`"pid"`). It is the interpreter that runs press, also when it was started
through a venv launcher.

**py-spy** (any supported Python, including 3.13–3.15; `uv tool install py-spy`):

```powershell
$daemonPid = Get-Content "$env:APPDATA\press\press.pid"
py-spy dump --pid $daemonPid                                   # what is each thread doing right now?
py-spy record --pid $daemonPid --duration 30 --format speedscope -o "$out\daemon.json"   # repeat the hotkey during these 30 s
py-spy top --pid $daemonPid                                    # live view
```

The daemon is idle most of the time and py-spy drops idle frames by default
— but per its README, on Windows calls blocked on I/O are not yet recognised
as idle, so the pipe server's thread waiting in `ConnectNamedPipe` shows up
as busy. Ignore that stack (`py-spy dump` shows which thread it is). `--idle`
includes every waiting frame. Open `speedscope` output at
<https://www.speedscope.app> or use `--format flamegraph -o daemon.svg`.

**`profiling.sampling`** (Python 3.15+, standard library):

```powershell
.venv\Scripts\python.exe -m profiling.sampling attach -a --flamegraph -d 30 -o "$out\daemon.html" $daemonPid
```

`-a` (`--all-threads`) is essential: by default only the main thread is
sampled, and the daemon's main thread runs the tray loop — transforms run on
the worker and pipe threads. The default `--mode wall` includes waiting;
`--mode cpu` keeps only time spent on CPU. Use the interpreter that runs the
daemon (`.venv\Scripts\python.exe`): it must be the same Python minor
version as the daemon, and on Windows
it needs an elevated shell or `SeDebugPrivilege` to read another process's
memory. py-spy may need an elevated shell as well if attaching is refused.

**On a corporate PC, ask before attaching.** Reading another process's
memory is exactly what EDR products watch for; a profiler attach can raise
an alert or be blocked. Profile on a developer machine, or get the IT
department's approval first.

### 3. Deterministic profile of a foreground daemon — last resort

```powershell
press daemon stop
.venv\Scripts\python.exe -m cProfile -o "$out\daemon.pstats" -m press daemon run
# use it, then Quit from the tray icon; the profile is written on exit
```

Prefer sampling. A deterministic profiler slows every Python call,
including the pynput keyboard-hook callback, and Windows silently removes a
low-level keyboard hook whose callback exceeds `LowLevelHooksTimeout`
(at most 1000 ms since Windows 10 1709) — the hotkeys would stop working
with no error, and the profile would describe a broken daemon.

The same foreground form works for import timing
(`.venv\Scripts\python.exe -X importtime -m press daemon run 2> "$out\daemon-imports.txt"`)
when daemon start-up is slow; read only
the main-thread lines before the first worker starts, since the output can
interleave once threads run.

## Outside Python — Process Monitor and WPR

When the press stages add up to much less than what the user experiences,
the time is being spent outside the interpreter: an endpoint agent
inspecting file opens, another application holding the clipboard open, a
slow disk.

- **[Process Monitor](https://learn.microsoft.com/en-us/sysinternals/downloads/procmon)**
  (Sysinternals): filter on *Process Name* `python.exe` / `press.exe` and
  enable the *Duration* column. It shows every file and registry access with
  its time, which is where the CLI's file-open count turns into milliseconds
  on a specific machine, and thread stacks show which agent's driver sits
  under an operation.
- **[Windows Performance Recorder](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options)**
  (WPR, ships with Windows; analyse in Windows Performance Analyzer) records
  system-wide CPU, file I/O, and context switches with ETW. Run from an
  elevated prompt:

  ```console
  wpr -start GeneralProfile -start FileIO
  # reproduce the slow action a few times
  wpr -stop "%TEMP%\press-perf\out\press-slow.etl" "press hotkey slow"
  ```

  `wpr -profiles` lists the built-in profiles; `wpr -cancel` discards a
  recording. An ETL file is a system-wide recording (other processes, file
  paths, window titles): treat it as confidential and do not attach it to a
  public issue. Like a profiler attach, a system-wide trace on a corporate
  PC needs the IT department's approval first.

`python -X perf` / `-X perf_jit` (perf trampolines) are Linux `perf`
features and do nothing on Windows.

## Recording results

Paste a summary like this into the PR that claims the improvement:

```text
press <commit> / CPython 3.15.0 / venv | press.exe / daemon off | on
Windows 11 26300 / agents: [Microsoft Defender AV]
hyperfine -N --warmup 3 --runs 30 "python -m press upper hello"
  before: 118.4 ms ± 3.1   after: 96.2 ms ± 2.8
press trace (median of 20): read 0.0 / delegate 0.0 / transform 2.6 / write 0.0 ms
```

Same machine, same procedure, before and after — otherwise the two numbers
measure different things.

## References

Checked 2026-10-29.

- CPython 3.15 — [`profiling`](https://docs.python.org/3.15/library/profiling.html),
  [`profiling.sampling`](https://docs.python.org/3.15/library/profiling.sampling.html),
  [command line `-X importtime`](https://docs.python.org/3/using/cmdline.html#cmdoption-X),
  [`timeit`](https://docs.python.org/3/library/timeit.html),
  [audit events](https://docs.python.org/3/library/audit_events.html),
  [logging HOWTO — Optimization](https://docs.python.org/3/howto/logging.html#optimization)
- [py-spy](https://github.com/benfred/py-spy) 0.4.2 (supports CPython 3.3–3.15)
- [hyperfine](https://github.com/sharkdp/hyperfine)
- [PyInstaller — specifying Python interpreter options](https://pyinstaller.org/en/stable/spec-files.html#specifying-python-interpreter-options)
- Microsoft — [Process Monitor](https://learn.microsoft.com/en-us/sysinternals/downloads/procmon),
  [WPR command-line options](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options),
  [`LowLevelKeyboardProc` (`LowLevelHooksTimeout`)](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc)
