# BWAPI collector

Windows-side external BWAPI client that emits the same TransitionV1 JSONL contract consumed by the Python learner.

## Modes

### Live player view

Does not enable `CompleteMapInformation` and excludes enemy/neutral units that are not visible to the evaluated player.

```powershell
BWAPICollector.exe --mode live --observability player --output C:\\starcraft-ai-data\\live.jsonl
```

### Replay player view

Replay mode can now use an arbitrary replay player as the point of view.

BWAPI 4.4.0 computes `Unit::isVisible(player)` for replay participants, so the collector emits only currently visible enemy/neutral state.

```powershell
BWAPICollector.exe `
  --mode replay `
  --observability player `
  --player-id 0 `
  --horizon-frames 8 `
  --output C:\\starcraft-ai-data\\reference.jsonl
```

The replay player-view reference deliberately does not synthesize last-seen memory. It is intended to be the authoritative current-visible-state signal used to validate the headless extractor.

### Privileged replay

For debugging only:

```powershell
BWAPICollector.exe --mode replay --observability privileged --player-id 0 --output C:\\starcraft-ai-data\\privileged.jsonl
```

Never compare privileged output against the non-cheating track.

## Action grouping

BWAPI exposes each unit's last command individually. A single human group command can therefore appear on many units in the same frame.

The collector groups commands with the same frame, command type, target, target position, and unit/tech/upgrade argument, then emits one action with multiple `actor_unit_ids`.

## Transition timing

Supported commands create action records, then the state is observed again after `--horizon-frames` (default 8). Unsupported command types are skipped rather than incorrectly coerced into the V1 action vocabulary.

## Replay explored_fraction

BWAPI's public replay tile API exposes replay-wide visibility/exploration rather than an arbitrary player's exact tile grid.

The reference therefore records `explored_fraction=0` in replay mode. This field is intentionally excluded from backend promotion checks.

## Atomic output

Output is written to `<output>.tmp` first and renamed only after the shard is complete.

## CI

GitHub-hosted runners do not contain StarCraft. The Windows workflow compiles the runtime collector, builds a contract self-test, emits TransitionV1 JSONL, and validates that shard on Linux.

The actual runtime cross-validation is M1-C's final local gate.
