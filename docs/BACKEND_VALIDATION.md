# BWAPI ↔ headless backend validation

The headless replay engine is fast enough for large-scale extraction, but speed is not evidence that its state matches the real game.

M1-C therefore treats the Windows BWAPI collector as the reference backend.

## One-replay validation protocol

Use exactly the same:

- replay;
- perspective player id;
- 8-frame horizon;
- TransitionV1 schema.

Produce:

```text
reference.jsonl  <- real StarCraft + BWAPI
candidate.jsonl  <- headless bw-engine + real game data
```

Then run:

```bash
uv run --extra cpu scai compare-backends \
  reference.jsonl \
  candidate.jsonl \
  --output backend-comparison.json
```

The report compares actions by frame/type and states by:

- action alignment;
- actor-count agreement;
- action target-position error;
- visible unit precision/recall;
- same-type/owner nearest-unit position error;
- HP error;
- minerals/gas;
- supply;
- state frame alignment.

Episode-local unit ids are not required to match. Visible units are matched by owner/type and spatial proximity.

## Promotion thresholds

The default gate is intentionally strict:

- at least 20 aligned actions;
- >=95% action alignment;
- <=0.5 actor-count MAE;
- <=16 px action target-position MAE;
- >=97% visible-unit precision and recall;
- <=8 px unit-position MAE;
- <=1 HP MAE;
- <=1 mineral/gas MAE;
- exact supply and frame alignment.

These thresholds are a **promotion rule**, not a claim that the current headless engine already satisfies them.

Use:

```bash
uv run --extra cpu scai compare-backends \
  reference.jsonl candidate.jsonl \
  --require-promotion
```

to return a failing exit code when any gate is missed.

## Player-observable replay extraction

BWAPI 4.4.0 internally computes per-player visibility flags during replays. The reference collector therefore uses `unit->isVisible(perspective)` and emits only currently visible enemy/neutral state for the player-observable track.

The BWAPI reference intentionally does **not** synthesize last-seen enemy memory. Backend comparison only evaluates currently visible units. Memory can be reconstructed independently by the learner or extractor without contaminating the reference current-state signal.

## Why explored_fraction is excluded from the promotion gate

BWAPI's public replay tile visibility API exposes replay-wide map visibility rather than the arbitrary perspective player's exploration grid. The reference collector records replay `explored_fraction=0` instead of pretending that aggregate replay visibility is player-specific.

The headless engine may still emit a per-player exploration fraction, but this field is not used for backend promotion until an authoritative perspective-specific BWAPI source is available.

## Local work left

CI can compile and test every component, but it cannot legally host the user's StarCraft installation.

One real local reference run is still required. After it exists, the comparison itself is fully automated.
