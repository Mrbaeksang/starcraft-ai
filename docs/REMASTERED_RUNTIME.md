# Current Battle.net runtime probe

The product target is an agent that itself plays humans through current
Battle.net public matchmaking and ladder. This probe only establishes that a
background window can be observed and addressed with keyboard messages. It is
not a game-playing runtime.

## Local evidence, 2026-09-29

- Client: `C:\Program Files (x86)\StarCraft\x86_64\StarCraft.exe`, version
  `1.23.10.13515`.
- Microsoft's [winapp CLI v0.7.0](https://github.com/microsoft/winappCli/releases/tag/v0.7.0)
  captured the `Brood War` window at 1920×1080 while `isForeground=false`.
  The local PNG was visually checked as the Battle.net lobby, rather than an
  occluding browser or a black frame. The PNG stays outside this repository.
- A three-second, 15fps window recording reported `mode=wgc`, 45 samples,
  `achievedFps=14.985`. This is capture cadence in a mostly static lobby, not
  policy inference or end-to-end action-loop throughput.
- A targeted `post-message` key typed one `x` into the lobby's chat input while
  the game was in the background; a second targeted Backspace removed it.
  Neither message was sent to chat. The effect was checked by window capture.
- GDI `gdigrab` of the same HWND returned a black frame.
- A posted mouse click did **not** activate the intended button; it selected a
  channel-list row instead. Mouse targeting, unit selection, in-game commands,
  public matchmaking, and ladder play remain unverified. Do not use posted
  mouse events as gameplay input based on this probe.

The machine-readable evidence record is
[`data/probes/remastered-window-2026-09-29.json`](../data/probes/remastered-window-2026-09-29.json).
It excludes the screenshots because the logged-in lobby contains personal
account and channel information.

## Reproduce background capture

Download the x64 release of Microsoft's winapp CLI to a Windows path, then on
the Windows/WSL2 machine run:

```bash
uv run --extra cpu scai probe-remastered-window \
  --winapp /mnt/c/path/to/winapp.exe \
  --output /mnt/c/Users/<you>/AppData/Local/Temp/scai-frame.png
```

The command finds exactly one `StarCraft` process window titled `Brood War`,
captures only that HWND without `--focus`, and reports the image hash and
whether a new PNG was written while the game stayed out of the foreground. It
sends no input or matchmaking command. The command reports
`content_visually_verified=false` because it cannot judge the pixels; a person
must inspect the local PNG and record that finding separately. A valid PNG or
window listing alone is not proof of meaningful game pixels.

For a repeatable keyboard check, first confirm on the captured image that the
Battle.net lobby chat input is focused. Get the current HWND with
`winapp.exe ui list-windows -a StarCraft --json`, then run the following against
that HWND while another app remains foreground:

```text
winapp.exe ui send-keys text=x --window <HWND> --via post-message --json
winapp.exe ui screenshot --window <HWND> --output <local-temp-path> --json
winapp.exe ui send-keys backspace --window <HWND> --via post-message --json
winapp.exe ui screenshot --window <HWND> --output <another-local-temp-path> --json
```

Inspect both local screenshots to confirm `x` appeared and was removed. Do
not press Enter in this probe because it would send a public chat message. The
Python `WinAppWindow.send_background_keys` method rechecks process identity
and foreground state around each targeted message, but the visible effect
still requires observation.

## Next gate

Build the version-locked [public Remastered adapter](../runtime/remastered_adapter/README.md)
to read player-observable live state and issue verified game commands. A
foreground input bridge may handle lobby menus and diagnostics, but must not
stand in for the match policy loop. Validate a local game before automatic
entry into a public Melee room and a full human match. Ranked remains a later
gate while unavailable in the current client. The offline BWAPI/replay
pipeline does not supply a verified live interface for this client.
