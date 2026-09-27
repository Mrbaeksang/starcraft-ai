# Benchmark protocol

This file defines what a credible public result should contain.

## Four separate questions

Do not collapse these into one score:

1. **Representation** — does the latent state retain control-relevant information?
2. **Dynamics** — can the model predict useful future latent states?
3. **Planning** — does imagination improve decisions at fixed compute?
4. **Game strength** — does the final agent win under a defined opponent pool?

## Minimum report

Every result table should include:

- commit SHA;
- dataset manifest/hash;
- train/validation/test split;
- observability mode;
- model parameter count;
- seed count;
- hardware;
- PyTorch/CUDA versions;
- transitions or environment steps;
- wall-clock time;
- peak VRAM;
- exact evaluation opponents/protocol.

## Early M2 metrics

Recommended initial probes:

- next-latent cosine error on held-out transitions;
- multi-step latent rollout degradation;
- linear probe: minerals/gas/supply;
- linear probe: army value;
- linear probe: tech state;
- terminal calibration;
- reward MAE;
- examples/sec and peak VRAM.

## Planning metrics

For M3, compare at equal planning budgets:

- no planning;
- random shooting/CEM baseline;
- proposed planner;
- broken/shuffled dynamics control.

Report both decision quality and wall-clock inference cost.

## Game-strength reporting

A single win-rate number is not enough.

Report:

- opponent names/versions;
- maps;
- races/matchups;
- games per cell;
- side/seed handling;
- confidence intervals;
- whether any privileged information was enabled.
