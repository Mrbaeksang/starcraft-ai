# Data card

## Purpose

Track every dataset source, transformation, observability assumption, and split used by the project.

## Data layers

### Historical structured pretraining

**StarData**

Upstream reports 65,646 Brood War games and large frame/action dumps. It is treated as historical distribution data, not current-meta ground truth.

### Current distribution

The repository tracks recent competitive map pools and fetches bounded high-MMR CWAL replay snapshots.

The first pinned snapshot is:

`data/snapshots/cwal-2026-09-28-2400plus.json`

Raw external replay files are short-lived artifacts unless redistribution permission is explicit.

### Real regression fixture

`tests/fixtures/larva_vs_mini.rep`

This is included with pinned upstream provenance for parser/data-contract regression. It is not a 2026 current-meta sample.

## Canonical future record

The learner-facing M1 format will be versioned around:

```text
EpisodeMetadataV1
ObservationV1
ActionV1
TransitionV1
```

A transition represents:

```text
observation_t + action_t -> observation_t+1
```

## Observability

The non-cheating track must not expose hidden enemy current state.

Allowed information can include:

- currently visible enemy state;
- previously observed information represented as memory/belief;
- player-owned state;
- map knowledge consistent with the evaluation protocol.

Privileged full-state experiments must be explicitly labeled and reported separately.

## Splitting

Do not randomly split neighboring transitions.

Primary splits are episode-level. Stronger generalization experiments should hold out players, maps, matchups, or time periods.

## Licensing / redistribution

This repository does not redistribute Blizzard game binaries or commercial assets.

External replay availability is not assumed to imply redistribution rights. Provenance and hashes are recorded separately from the raw files where required.
