# FAQ

> **Applies to:** both (CLI and daemon).

## A `press` command sometimes takes 2–3 seconds

Most `press` commands finish in well under a second. If one of them
**occasionally** takes 2–3 seconds (for example `press tm -c -C`), and
especially on a slower PC, please collect the measurements below and send
them to us. The numbers tell us which stage is slow on *your* machine, so we
can fix the actual cause instead of guessing.

The measurements never include your clipboard contents — only timings,
character counts and command names. The commands below send the
transformed text to `$null` so it does not appear on screen either.

### 1. Turn on tracing

```powershell
press trace on
```

### 2. Reproduce the slow command

Run the command that was slow, in the same situation where it was slow
(for example after the PC has been idle for a while). Repeat it 3–5 times:

```powershell
press tm -c -C > $null
```

Each run prints one line like this:

```text
press: trace read=1.2ms delegate=3.4ms write=0.5ms
```

Copy every `press: trace …` line.

### 3. Measure the total time

```powershell
(Measure-Command { press tm -c -C *> $null }).TotalMilliseconds
```

Run it 3–5 times as well and copy the numbers. The trace line only covers
the work inside press. If the total is much larger than the trace values,
the time went into starting the process itself.

### 4. Compare with two features turned off

```powershell
# Without the daemon (the CLI transforms the text itself)
$env:PRESS_NO_DAEMON = "1"
(Measure-Command { press tm -c -C *> $null }).TotalMilliseconds
Remove-Item Env:PRESS_NO_DAEMON

# Without the undo snapshot that -C saves before overwriting the clipboard
$env:PRESS_NO_UNDO = "1"
(Measure-Command { press tm -c -C *> $null }).TotalMilliseconds
Remove-Item Env:PRESS_NO_UNDO
```

### 5. If the daemon is running, copy its log

```powershell
press daemon logs --level debug
```

Copy the lines from the time you reproduced the problem. They look like
`pipe.serve elapsed_ms=…`.

### 6. Turn tracing off

```powershell
press trace off
```

### What to send us

Open a [bug report](https://github.com/tay2501/textkit2/issues/new?template=bug_report.yml)
and include:

- The `press: trace …` lines (step 2)
- The total times (steps 3 and 4)
- The daemon log lines, if the daemon was running (step 5)
- The output of `press --version`
- How you installed press: the release `.exe`, or Python (`uv` / `pip`)
- Whether the daemon was running (`press daemon status`)
- Detected security software: the `monitoring_agents` field of
  `press daemon status --json`
- The PC: CPU, RAM, and whether the system drive is an HDD or SSD
- When the delay happens: every time, the first run after the PC has been
  idle, or at random

### How we read the results

| What you see | Likely cause |
|---|---|
| `delegate=` is about 2000 ms | The CLI waited for the daemon, gave up after its 2-second timeout and transformed the text itself |
| The total time is much larger than the trace values | Process startup (Python start-up, security software scanning the files it opens) |
| `write=` is large, or `PRESS_NO_UNDO=1` is clearly faster | Saving the undo snapshot before overwriting the clipboard |
| `read=` is large | Another application is holding the clipboard, or security software inspects clipboard access |

For general tuning on PCs with security software, see
[Running press under endpoint security agents](edr-environments.md).
