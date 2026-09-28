# Model card

## Model name

StarCraft AI — Structured Latent World Model (research scaffold)

## Status

**Experimental / pre-training scaffold.**

There is currently no released competitive gameplay checkpoint.

## Intended use

Research on:

- structured entity representations for Brood War;
- action-conditioned latent dynamics;
- predictive representation learning;
- model-based planning;
- later latent-action and self-play experiments.

## Current architecture

The M0 scaffold contains:

- entity feature projection;
- Transformer entity encoder;
- action-type embedding + action-argument encoder;
- action-conditioned latent predictor;
- EMA target encoder;
- reward head;
- terminal head.

This model is currently validated on deterministic synthetic transitions, not real-game predictive benchmarks.

## Planned baselines

Before promoting the proposed architecture:

1. direct next-feature baseline;
2. recurrent/RSSM or Dreamer-style baseline;
3. current EMA target-representation model;
4. simple planning baseline;
5. broken/shuffled-dynamics negative control.

## Inputs

Long-term inputs are structured player-observable game state:

- units/entities;
- resources and supply;
- upgrades/tech;
- map/region features;
- visibility/exploration;
- recurrent belief/memory.

Broadcast pixels are not the primary control input.

## Actions

Planned action representation is structured and masked:

- acting unit/entity set;
- command type;
- target entity or target position;
- optional production/build/tech argument.

## Limitations

- no validated competitive checkpoint;
- no demonstrated advantage over Dreamer/RSSM or TD-MPC-style baselines;
- headless replay reconstruction still needs M1 validation;
- current historical/current replay distributions differ;
- Brood War partial observability makes leakage prevention critical.

## Evaluation

See `docs/BENCHMARKS.md` and `docs/REPRODUCIBILITY.md`.
