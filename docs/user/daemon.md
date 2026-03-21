# Daemon Mode

The `press` daemon runs in the background and listens for global hotkeys.

## Starting and stopping

```bash
press daemon start      # start in background, show tray icon
press daemon stop       # stop
press daemon status     # print "running" or "stopped", exit code 0 or 1
press daemon restart    # stop + start (reloads config and dictionary)
```

## Tray icon

When the daemon is running, a tray icon appears in the Windows system tray.

Right-click the icon for:
- **Reload config** — reload `config.toml` without restarting
- **Reload dictionary** — reload TSV files without restarting
- **HOLD: on/off** — toggle clipboard protection
- **Quit** — stop the daemon

## HOLD mode

When HOLD is active, the tray icon changes to indicate protection.
Any clipboard change is detected and immediately restored to the held content.

```bash
# Via hotkey: Prefix + H
# Via CLI:
press hold    # toggle from terminal too
```

## Auto-start on login (optional)

To start the daemon automatically when you log in to Windows,
add a shortcut to the Startup folder:

1. Press `Win+R`, type `shell:startup`, press Enter
2. Create a shortcut: target = `press daemon start`

Or use the tray icon menu: **Start with Windows** (if implemented).
