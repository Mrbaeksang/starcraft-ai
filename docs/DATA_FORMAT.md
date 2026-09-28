# TransitionV1 data format

M1 defines the stable boundary between replay/runtime extraction and model training.

## Principle

Collectors may change. The learner-facing contract must not silently change with them.

```text
replay / BWAPI / headless engine
            ↓
       extractor adapter
            ↓
      TransitionV1 JSONL
            ↓
 compact NPZ training shard
            ↓
       PyTorch loader
```

## Records

### EpisodeMetadataV1

Describes provenance and the point of view used for one game:

- episode id;
- source;
- map;
- evaluated player;
- races;
- observability mode;
- optional replay SHA-256.

### ObservationV1

Stores raw structured values, not model-normalized values:

- frame;
- player resources/supply;
- map dimensions;
- exploration fraction;
- upgrades/tech ids;
- observed unit records.

Coordinates and HP remain lossless integer game values. Normalization is a model-loader responsibility.

### UnitObservationV1

A hidden enemy unit is allowed only as explicit memory:

```text
visible = false
position_source = "last_seen"
last_seen_frame = ...
```

The non-cheating schema therefore cannot silently label a hidden enemy coordinate as a current coordinate.

### ActionV1

A structured action contains:

- acting unit ids;
- command type;
- optional target unit;
- optional target position;
- optional unit/tech/upgrade argument.

Impossible structural combinations are rejected by validation.

### TransitionV1

```text
observation_t + action_t -> observation_t+1
```

The action frame must lie between the two observation frames.

## Compatibility policy

Version 1 parsing is intentionally strict.

**Unknown fields are rejected.** A collector cannot silently start feeding a new feature into training. A data-contract change requires an explicit schema version or migration.

This is stricter than a typical web API because silent feature drift can invalidate research results.

## JSONL

Canonical JSON uses:

- UTF-8;
- sorted keys;
- no NaN/Infinity;
- compact separators;
- one transition per line.

This makes hashes deterministic and diffs inspectable.

## Compact training format

For CPU/GPU loading, `pack_npz_v1` converts JSONL transitions into a compressed NumPy NPZ shard.

Variable-length entity sets are represented as packed entity arrays plus offsets:

```text
observation_units
observation_unit_offsets
next_observation_units
next_observation_unit_offsets
```

The NPZ representation is a compact training-oriented alternative to Parquet/Arrow that adds no large dependency beyond NumPy, which is already required by the project.

JSONL remains the canonical interchange/debug format; NPZ is derived and reproducible.

## Fixture

`tests/fixtures/transitions_v1.jsonl` is synthetic and redistribution-safe.

Its manifest pins:

- byte length;
- transition count;
- SHA-256;
- episode metadata.

A fresh Linux GitHub runner can validate and load it without StarCraft installed.
