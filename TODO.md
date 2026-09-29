# Autonomous Remastered bot

## Definition of done

On the installed current StarCraft: Remastered client, one bot process starts
from the Battle.net lobby, filters **public Melee** rooms, chooses an open
**Fighting Spirit (투혼)** or **Python (파이썬)** room, joins it, and plays a human
opponent to a recorded win/loss result. It handles race selection, game start,
economy, production, combat, and game end without an assistant, operator clicks,
or a manually executed sequence of computer-use calls. It must record the
client build, map, room identity, action timestamps, result, and replay or local
evidence. An actual completed public human game is the acceptance test.

The longer-term Pluto-like target is a trained policy that owns macro and
micro. A scripted baseline may prove the runtime but does not complete that
learning target. Ranked play remains a later gate because the current client
does not presently offer a usable Ranked entry; a private lobby or legacy
1.16.1/BWAPI match does not complete the public-room gate.

## Ordered work

### 0. Establish the current-client boundary

- [x] Verify client build `1.23.10.13515` and live Battle.net lobby.
- [x] Capture the target window through WGC at 1920×1080; record 15fps window
  capture evidence.
- [x] Verify targeted keyboard input; remove the test character without chat.
- [x] Verify foreground mouse click through computer-use in the lobby (News
  dialog opened). This proves UI targeting only; it is too slow for gameplay.
- [ ] Prove a **native, persistent** Windows input process can click exact
  client coordinates and issue hotkeys with measured latency. This is a menu
  automation/fallback transport, not proof of game-state/action integration.
- [ ] Replace per-command PNG/CLI startup with a continuous frame stream for
  lobby recognition and visual checks; log latency and dropped frames.

### 0A. Build and publish a current-client game adapter (primary path)

- [x] Pin the exact `1.23.10.13515` binary identity and create a versioned
  runtime manifest. Reject unknown builds instead of applying stale offsets.
- [x] Open the matching Windows process read-only and read its in-memory PE
  header. This proves attachment, not game-state extraction. See
  [`runtime/remastered_adapter/README.md`](runtime/remastered_adapter/README.md).
- [x] Audit the open [BWAPI Remastered port](https://github.com/NomaDamas/starcraft-api/blob/main/docs/remastered-porting.md)
  and its LGPL license. The [file-level audit](docs/REMASTERED_ADAPTER_AUDIT.md)
  records reusable contracts and the missing live proofs; use its negative
  gates as test cases. Recheck upstream changes before integrating code.
- [ ] Attach a resident x64 adapter to the current client and read an active
  match frame/tick, local player, resources, own units, visible enemy units,
  orders, map coordinates, and visibility. Prove that hidden enemy data cannot
  enter the policy observation.
- [ ] Deliver one Move command through the game's own command path and observe
  the selected unit move in a local match. Then prove Attack, Train, Build,
  selection, and camera actions individually. A queued byte write without
  visible behavior does not pass.
- [ ] Repeat command proofs in a multiplayer custom game and verify turn
  synchronization, no desync, and normal replay generation. Keep live proof
  records tied to client build, process ID, game frame, selected unit, command,
  and observed result.
- [ ] Publish a small versioned `ObservationV1` / `ActionV1` bridge and a
  headless policy-process protocol. The adapter must run the policy locally on
  a bounded game-frame schedule; the assistant must not sit in the match loop.
- [ ] Add build, replay-based contract tests, and a live smoke command to CI
  where possible. Windows game assertions remain a separately recorded local
  gate until a game installation is available in CI.

### 1. Enter public Melee rooms automatically

- [ ] Detect lobby, custom-game list, room lobby, loading, in-game, and result
  states from player-visible frames; fail closed on unknown screens.
- [ ] Set the public room filter to Melee; read visible room/map/player counts
  and refresh when none match. Never infer room identity from a fixed row index.
- [ ] Join only open, non-passworded Fighting Spirit/Python rooms. Verify the
  map and Melee type again inside the room. Handle full/closed/disappeared
  rooms, timeout, and disconnect with bounded retries.
- [ ] Select one declared race automatically and wait for human host start.
  Support a host-created room as a separate fallback, while preserving the
  automatic-join acceptance test.
- [ ] Dry-run the whole menu state machine on stored frames, then on the live
  client without starting a match; log every decision and state transition.

### 2. Make a playable local baseline

- [ ] Define observations only from information available to the player and
  compare the adapter output with visible screen/HUD/minimap evidence on
  Fighting Spirit/Python. Measure unit/action mapping errors.
- [ ] Expose unit selection, build, train, move, attack, and camera actions
  through the verified adapter. Reject stale frames and wrong-process actions.
- [ ] Implement one-race economy/production/combat baseline to validate the
  runtime. It may use deterministic rules; it is not the final trained policy.
- [ ] Complete a full local Melee game with no assistant actions. Preserve
  frame/action/result logs and inspect failures.

### 3. Train a Pluto-like policy

- [ ] Establish a real observation/action training set aligned to the live
  interface. Resolve the current StarData actor-identity mismatch before using
  it as a supervised transition source.
- [ ] Train an imitation or self-play policy that controls macro and micro;
  compare it against the deterministic baseline on held-out maps/opponents.
- [ ] Keep inference local and bounded by a measured game-step budget (initial
  target: one decision every six game frames, p95 end-to-end under 250 ms).
- [ ] Add recovery for inference failure, stuck UI, lost connection, and game
  end. A failure must produce a logged result, not silent manual takeover.

### 4. Public human acceptance

- [ ] Bot starts from the Battle.net lobby and joins a public Melee room on
  투혼 or 파이썬 without operator input.
- [ ] Bot completes at least one full human game, with replay/result and
  synchronized observation/action evidence showing autonomous control.
- [ ] Repeat across both maps and multiple opponents; report join reliability,
  action latency, disconnects, and win/loss honestly.
- [ ] Attempt ranked play only when the current client exposes a usable path;
  keep it distinct from the public custom-room completion claim.

## Current blocker

The repository has model/replay research and a current-client capture probe,
but no verified Remastered state/command bridge, autonomous match loop, or
trained policy. [Pluto's public release](https://github.com/tscmoo/pluto)
requires Brood War 1.16.1 + BWAPI; a reported Remastered ladder adaptation is
evidence that such an adapter is possible, but its implementation is not
public. The experimental
[Remastered API port](https://github.com/NomaDamas/starcraft-api/blob/main/docs/remastered-porting.md)
provides a starting architecture and fail-closed contracts, but does not yet
provide live-proven command parity. The adapter proof above is the critical
path; screen clicks alone cannot complete it.
