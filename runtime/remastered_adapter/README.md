# Remastered adapter: first live boundary

This is the start of a public, version-pinned adapter for the current Windows
client. The current code proves process identity and read-only attachment. It
does **not** read game state, issue game commands, synchronize multiplayer
turns, or load a bot. Those are explicit gates in [`TODO.md`](../../TODO.md).

## Verified client

- Executable: `C:\Program Files (x86)\StarCraft\x86_64\StarCraft.exe`
- File version: `1.23.10.13515`
- SHA-256: `ce3ab05dc9a6aa35418947e5d95e19651ad6fbcd5e2c1856cd729c5b7c31281c`
- Manifest: [`manifests/1.23.10.13515.json`](manifests/1.23.10.13515.json)

The Windows PowerShell probe verifies version and hash, opens the running
process read-only, and reads the in-memory PE header. It prints separate false
flags for game-state, command, and multiplayer proof:

The local result is recorded in
[`data/probes/remastered-attach-2026-09-29.json`](../../data/probes/remastered-attach-2026-09-29.json).

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/windows/attach_probe.ps1 `
  -ManifestPath runtime/remastered_adapter/manifests/1.23.10.13515.json
```

The Go probe checks the executable hash against the manifest and builds a
Windows x64 executable. Its `manifest_version` field is a manifest label, not
an independently read Windows file version. The PowerShell live probe checks
both the file version and hash.

The read-only [counter scanner](../windows/state_probe.ps1) also verifies the
build, locates the executable's `.data` section from its PE table, and samples
changing 32-bit values. It ran against the installed process. Its candidates
are diagnostic addresses only: none is validated as a match frame, unit array,
or player state. The scanner always reports those proof fields as false.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/windows/state_probe.ps1 `
  -ManifestPath runtime/remastered_adapter/manifests/1.23.10.13515.json
```

```bash
cd runtime/remastered_adapter
go test ./...
GOOS=windows GOARCH=amd64 go build -o remastered-adapter.exe .
```

On the development host, Windows Code Integrity rejected this newly built
unsigned executable (event IDs 3033/3077, enterprise signing requirement).
The PowerShell probe ran successfully on the same process without changing
that host policy. This is an execution-environment observation, not evidence
that the game itself prevents an adapter.

## Implementation direction

The [persistent foreground bridge](foreground_bridge.py) can request 1920×1080
frames and click through one Windows PowerShell process; its protocol is tested
without a game in CI. A live 30-frame lobby sample had p95 capture time 68.96 ms,
and clicks opened the custom-game list and returned to the lobby. The bridge
checks the same version and SHA-256 as the attach probe before accepting input.
Those click timings were measured before a 50 ms hold was added; current click
latency has not been remeasured. See the
[local evidence](../../data/probes/remastered-foreground-2026-09-29.json).
The bridge requires the game in front and exposes screen pixels rather than
units or resources. It is a lobby transport and a temporary visual fallback.

Use the open [BWAPI Remastered runtime contracts](https://github.com/NomaDamas/starcraft-api/blob/main/docs/remastered-porting.md)
as a reference for versioned bindings and behavior proof. That port currently
marks active game-state extraction, command delivery, and multiplayer parity
unproven. We have not copied its LGPL code into this MIT repository. A
minimal public observation/action surface should be proved on this exact
client before broader BWAPI parity or policy training is claimed. The
[file-level audit](../../docs/REMASTERED_ADAPTER_AUDIT.md) gives the next
vertical slice and the upstream boundaries.
