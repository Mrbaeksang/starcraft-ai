# Headless replay extraction

The project now has two independent replay-state paths.

## 1. BWAPI collector

The Windows BWAPI collector observes the actual game runtime and is the authoritative reference path.

Advantages:

- actual Brood War state;
- direct BWAPI visibility semantics;
- no simulated-physics approximation.

Limitations:

- requires a compatible local StarCraft/BWAPI runtime;
- not suitable for ordinary public GitHub-hosted CI.

## 2. Headless bw-engine extractor

The Rust extractor parses real `.rep` files and replays their commands through a selective open-source Brood War engine.

Advantages:

- headless;
- Linux/CI friendly;
- deterministic;
- current and legacy replay format support;
- explicit per-player fog-of-war state.

Limitations:

- the engine is intentionally selective, not a byte-for-byte Blizzard engine;
- some replay command semantics remain approximate;
- real `.dat` and tileset files improve fidelity but do not remove the need for BWAPI cross-validation.

## Promotion rule

No headless dataset is called authoritative real-state training data until:

1. the same replay is extracted through BWAPI;
2. aligned frames are compared for units, resources, visibility, HP, and actions;
3. mismatch rates are published;
4. accepted tolerances are documented.

Until then:

- `synthetic-ci` output = pipeline validation only;
- `headless-real-gamedata` output = experimental data;
- BWAPI output = reference data.

This distinction prevents a fast simulator from silently becoming a false ground truth.
