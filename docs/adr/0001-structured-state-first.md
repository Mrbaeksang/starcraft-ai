# ADR 0001: Structured state first

Status: accepted

## Context

Brood War can be observed either through rendered pixels or through structured game interfaces/replay tooling.

Pixel-first training would add OCR, detection, tracking, camera selection, and observer-vision ambiguity before the control problem itself is addressed.

## Decision

The primary control/research track uses structured state:

- units/entities;
- resources/supply;
- tech/upgrades;
- map information;
- visibility;
- structured actions.

Broadcast video remains useful for current-strategy discovery and optional representation experiments, but is not the canonical control label source.

## Consequences

Positive:
- more compute goes into dynamics/control rather than reconstructing pixels;
- action/state labels can be audited;
- fog-of-war leakage can be tested explicitly;
- single-GPU research becomes more practical.

Tradeoff:
- conclusions apply first to structured-interface agents, not vision-only agents.
