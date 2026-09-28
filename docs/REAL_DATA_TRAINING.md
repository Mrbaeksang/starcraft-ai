# TransitionV1 training

The training path now consumes the same `TransitionV1` contract emitted by replay extractors.

```text
.rep
 ↓
BWAPI or headless extractor
 ↓
TransitionV1 JSONL
 ↓
feature tensorizer
 ↓
MLP / recurrent baseline / JEPA-style model
```

## Entity tensor

Each state receives a global token plus up to 255 unit/entity tokens.

The 24 features encode:

- global-token marker;
- unit type;
- owner one-hot;
- normalized coordinates;
- HP ratio / max HP;
- shields / energy;
- order id;
- visibility and last-seen memory;
- last-seen age;
- minerals / gas;
- supply;
- explored fraction;
- frame progress;
- map dimensions.

Raw episode-local unit IDs are intentionally not treated as stable semantic features.

## Action tensor

Action type remains categorical.

Eight continuous/action-argument features encode:

- selected actor count;
- target-unit presence;
- episode-local target id;
- normalized target position;
- unit/tech/upgrade argument;
- frame progress;
- bias term.

This flat representation is a **baseline input**, not the final pointer-network action architecture.

## Smoke mode vs research mode

A single replay cannot produce a credible held-out generalization result.

Therefore:

```bash
scai train-data one-replay.jsonl --allow-single-episode-smoke
```

is explicitly marked `smoke_only=true`.

Without that flag, fewer than three episodes are rejected.

A claimable experiment must use episode-level train/evaluation partitions. Neighboring transitions from the same replay are never intentionally split across train and held-out evaluation.

## Models

`--model` supports:

- `mlp` — direct next-feature baseline;
- `recurrent` — small GRU dynamics baseline;
- `jepa` — current EMA target-representation model.

This lets the exact same replay dataset feed the baseline suite.

## Current status

The CI real-replay integration uses headless `synthetic-ci` state reconstruction only to prove end-to-end plumbing.

It is **not** reported as a real-data model result.

The first research result remains gated on an authoritative/cross-validated replay-state source.
