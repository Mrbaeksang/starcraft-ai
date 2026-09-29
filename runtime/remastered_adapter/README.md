# Remastered adapter: first live boundary

This is the start of a public, version-pinned adapter for the current Windows
client. The current code proves process identity and read-only attachment. It
does **not** read game state, issue game commands, synchronize multiplayer
turns, or load a bot. Those are explicit gates in [`TODO.md`](../../TODO.md).

The separate foreground UI bridge has now delivered Move, Gather, and Train
inputs in a private Fighting Spirit Melee game; the selected Probe moved, self
minerals rose, and the Nexus showed a Probe build queue. See the
[live command diagnostic](../../data/probes/remastered-live-commands-2026-09-29.json).
The assistant chose the screen coordinates. This does not prove that a policy
can choose actions, that the native game command path works, or that a bot can
complete a match.

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
or player state. The scanner always reports those proof fields as false. The
[`0x1090870` investigation](../../data/probes/remastered-counter-correlation-2026-09-29.json)
records a value that advanced by 24 per second during a private game and was
zero on the defeat screen. A paused replay falsified the frame hypothesis:
it kept advancing while the displayed replay time stayed at 02:12. Three
other `.data` values stopped on pause, but none is identified as a game frame.
An exploratory scan of 269 `.data` pointer/count/capacity triples also found
no active CUnit array after requiring readable sprite pointers.
The [resident state bridge](../windows/state_bridge.ps1) reads one candidate
RVA without restarting PowerShell for every snapshot. A local 30-request
post-match sample had p95 round-trip latency 2.38 ms; all values were zero.
Its protocol explicitly says `game_frame_proven=false`; the sampled address
must not be fed to a policy as an authoritative game frame.

The [resource diagnostic](../windows/resource_probe.ps1) reads eight
pointer-free resource pairs from this exact build at `.data` RVA `0xe801b4`
with a 1768-byte player-slot stride. [Paused replay comparisons](../../data/probes/remastered-resource-table-2026-09-29.json)
matched slot-zero minerals at three displayed values (50, 90, 186) and
slot-one gas at 216. An adjacent name table at RVA `0x106a008` with a
232-byte stride matched both displayed player names across those replay
points; `-ExpectedSelfName` resolves a candidate slot only on an exact,
unique ASCII match. This is a provisional native resource binding. One
slot-one mineral value disagreed with the replay HUD, and the local player
slot has not been proven for live multiplayer. By default the probe emits
only the uniquely matched candidate self resources; dumping all slots
requires `-ResearchAllSlots`. The result remains a diagnostic and must not
be used as a policy observation yet.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/windows/state_probe.ps1 `
  -ManifestPath runtime/remastered_adapter/manifests/1.23.10.13515.json `
  -WatchRva 0x1090870
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/windows/state_bridge.ps1 `
  -ManifestPath runtime/remastered_adapter/manifests/1.23.10.13515.json `
  -CandidateRva 0x1090870
# Send {"op":"snapshot"} and {"op":"quit"} as JSON lines on stdin.
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/windows/resource_probe.ps1 `
  -ManifestPath runtime/remastered_adapter/manifests/1.23.10.13515.json `
  -ExpectedSelfName baeksang100
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
