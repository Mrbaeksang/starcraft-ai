# Data acquisition

## Short version

Use three data layers:

1. **Structured historical pretraining** — large replay-derived datasets such as StarData.
2. **Current competitive distribution** — recent map pools, players, matchups, and source metadata.
3. **Our own BWAPI extraction** — the canonical labels for the model we evaluate.

Do not make broadcast video the primary source of state/action labels.

## Why YouTube is not the main training dataset

A broadcast video contains useful strategic evidence but hides or distorts information needed for control:

- observer camera shows only part of the map;
- UI overlays and production tabs vary;
- exact unit IDs/orders are unavailable;
- game speed and cuts can change;
- actions are not directly recoverable;
- observer vision may reveal information a player could not see.

Turning video into structured state would require a separate vision/OCR/tracking problem and could silently inject observer-only information.

Use video for:

- current strategy coverage;
- current map/player/matchup discovery;
- qualitative error analysis;
- optional representation experiments where the task explicitly uses pixels.

Use replay/BWAPI transitions for control labels.

## Current map pool seed

`data/sources/major_proleague_2026-09-17.json` tracks a directly verified September 2026 Major Proleague event with:

- Backrooms
- Octagon SE
- KnockOut
- Colorless Fate
- Odyssey RE
- Attitude SE
- Aiolos

Daily Major Proleagues continued through September 18, 2026. The September 17 event is used here because its map list was directly verified from the event page.

This is a **metadata seed**, not a claim that it is the only current tournament pool.

## Public video seed

`data/sources/youtube_seed_index.json` contains verified URLs from SOOP's 2026 ASL S21 and S22 coverage plus search queries for the recent Proleague map names.

The repository stores URLs and factual metadata only.

### Build a larger local metadata index

Install a current yt-dlp without adding it to the project environment:

```bash
uv tool install "yt-dlp==2026.8.19"
```

Then:

```bash
python scripts/index_youtube_metadata.py \
  --query "2026 스타크래프트 프로리그 KnockOut" \
  --query "2026 스타크래프트 프로리그 Backrooms" \
  --query "2026 스타크래프트 프로리그 Aiolos" \
  --limit 30 \
  --output data/local/proleague-youtube-index.json
```

`data/local/` is local-only and should not be committed.

This command requests metadata only; the script passes `--skip-download`.

## Media files

Do not bulk-download or commit third-party broadcast media unless you have an explicit right to do so.

If you independently have licensed/authorized local media for an experiment, keep it outside Git:

```text
data/local/videos/
```

and record provenance/license information in a local manifest.

## Historical structured source: StarData

The StarData project reports:

- 65,646 games;
- 1.535 billion frames;
- 496 million player actions;
- 8 dumped frames per second;
- about 365 GB compressed.

It is useful for historical pretraining but is not a drop-in substitute for current-map evaluation. Its upstream repository is archived, and its distribution/runtime differs from 2026 competitive play.

Do not start by downloading all 365 GB.

First implement a bounded subset experiment with a deterministic manifest.

## Canonical M1 dataset

Our own collector should eventually produce records like:

```text
episode
  metadata
    map
    players
    races
    replay hash
    observability mode

transition_t
  observation_t
  action_t
  observation_t+1
  reward components
  terminal
```

The **observation** must contain only information available to the evaluated player when using the non-cheating track.

## Data split strategy

Avoid random transition-level splitting; neighboring frames leak almost identical states.

Split at episode level. For stronger tests, additionally hold out:

- players;
- maps;
- matchups;
- time periods.

A useful current-distribution test is to pretrain broadly, then hold out one or more recent maps for evaluation.

## Training order

```text
StarData subset / older replay corpus
        |
        v
representation pretraining
        |
        v
our BWAPI replay extraction
        |
        v
current-map fine-tuning
        |
        v
held-out current-map evaluation
        |
        v
planning + self-play
```

Video metadata informs which current maps/players/strategies deserve coverage; it does not replace the structured labels.
