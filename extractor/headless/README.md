# Headless replay extractor

This is the CI-friendly replay-to-`TransitionV1` path.

It uses the MIT-licensed `broodwar-live/bw-engine` replay parser and selective headless game-engine implementation pinned to commit:

`befa5432c8749cdea196703c5b82c0f0fcfad2c5`

## Two modes

### Synthetic CI mode

```bash
cargo run --release --manifest-path extractor/headless/Cargo.toml -- \
  --replay tests/fixtures/larva_vs_mini.rep \
  --output artifacts/larva-mini.jsonl \
  --synthetic \
  --max-frames 3000
```

This mode uses the real replay command stream and map dimensions but synthetic unit/game tables and an all-walkable terrain model.

It exists to validate:

- real replay parsing;
- deterministic command replay;
- player-view memory schema;
- TransitionV1 generation;
- corruption/error behavior;
- CI integration.

**It is not scientific training data.**

The manifest explicitly reports `fidelity=synthetic-ci`.

### Local game-data mode

If the StarCraft installation exposes the small `arr/*.dat` and `tileset/*.{cv5,vf4}` files:

```bash
cargo run --release --manifest-path extractor/headless/Cargo.toml -- \
  --replay game.rep \
  --output game.transitions.jsonl \
  --game-data-root "/mnt/c/.../StarCraft"
```

This loads real unit, movement, weapon, tech, upgrade, order, and terrain tables.

The backend is still a **selective reimplementation**, not the authoritative Blizzard runtime. Its output remains experimental until cross-validated against the BWAPI collector on the same replay.

## Why keep both BWAPI and headless paths?

```text
BWAPI / real runtime
  = authoritative reference extraction

headless bw-engine
  = fast, reproducible, CI-friendly extraction
```

M1-C compares the two before headless output is promoted to real training data.

## Observability

The extractor simulates all players but emits transitions for one perspective player.

Enemy units are:

- emitted with current coordinates only while visible;
- remembered as `position_source=last_seen` after leaving vision;
- removed from memory when their last-known tile becomes visible and the unit is absent.

This directly matches the `TransitionV1` hidden-information contract.

## Known approximation

Replay right-click commands with a unit target are mapped to the headless engine's current attack command because the selective engine does not yet expose every Brood War order. Command translation coverage is recorded in the extraction manifest.
