# Public Remastered adapter audit

Checked against the public [starcraft-api Remastered port](https://github.com/NomaDamas/starcraft-api/blob/main/docs/remastered-porting.md) on 2026-09-29. Its source is LGPL-3.0. This repository uses its documented contracts as a reference and does not copy or link its source. If that changes, review the LGPL distribution and relinking obligations before publishing a binary.

| Upstream part | What it provides | What it does not prove for this client |
| --- | --- | --- |
| [`RemasteredRuntimeBackend.cpp`](https://github.com/NomaDamas/starcraft-api/blob/main/bwapi/Runtime/RemasteredRuntimeBackend.cpp) | Versioned manifest, runtime preflight, fail-closed production gate. | `probe()` and `open()` only report support when other live proofs exist; they do not themselves extract units or issue commands. |
| [`RuntimeProcessMemory.cpp`](https://github.com/NomaDamas/starcraft-api/blob/main/bwapi/Runtime/RuntimeProcessMemory.cpp) | Windows process open, `ReadProcessMemory`, and `WriteProcessMemory` primitives. | A readable process region is not a validated game structure. A successful write is not a synchronized StarCraft command. |
| [`RuntimeCommandQueue.cpp`](https://github.com/NomaDamas/starcraft-api/blob/main/bwapi/Runtime/RuntimeCommandQueue.cpp) | In-memory command queue representation. | No demonstrated delivery through the current client's turn/command path. |
| [`RuntimeResidentBridge.cpp`](https://github.com/NomaDamas/starcraft-api/blob/main/bwapi/Runtime/RuntimeResidentBridge.cpp) | Resident queue and proof validation format. | The verifier cannot create the resident adapter or live game evidence it expects. |

## Smallest useful vertical slice

1. Pin the installed executable hash and version; reject other builds. **Done** for `1.23.10.13515`.
2. Attach read-only and verify process identity plus an in-memory PE header. **Done** in [`attach_probe.ps1`](../runtime/windows/attach_probe.ps1); this is only a process-access proof.
3. In a local active match, identify a frame counter and local player through independently checked runtime bindings. Read minerals, gas, one own unit's identity/position/order, and one visible enemy; compare each with the HUD or replay. Record raw binding evidence without publishing a static address as a universal offset.
4. Verify observation filtering: an enemy outside current visibility must not appear in the policy observation, even if raw memory contains it.
5. Issue a single Move through the client's command/turn path, and show a matching in-game order and resulting movement. Repeat for Attack, Train, and Build. Record frame, unit, target, accepted command, and observed result.
6. Repeat Move and one production action in multiplayer, inspect replay and disconnect/desync behavior, then expose the proven subset through a versioned observation/action protocol.

No upstream claim, queue serialization test, or process-memory read substitutes for steps 3–6. The local host currently blocks a new unsigned Go executable through Windows Code Integrity; the read-only PowerShell probe works. A future resident binary needs an executable route on this host before live command proof.
