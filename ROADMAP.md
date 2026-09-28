# Roadmap

The roadmap is gated by evidence, not dates.

## M0 — Research scaffold ✅

- reproducible uv/PyTorch environment;
- CPU/CUDA profiles;
- model smoke training;
- CI, CodeQL, Dependabot;
- current replay acquisition;
- reference pins and research documentation.

## M1 — Trustworthy game data 🚧

Completed engineering:
- TransitionV1 contract;
- deterministic JSONL/NPZ formats;
- synthetic fixture + hashes;
- BWAPI collector compile/cross-OS contract CI;
- extraction/hash/leakage/throughput audit tooling.

Remaining scientific/runtime gate:
- one real player-observable replay extraction with deterministic hashes and audited fog-of-war semantics.

## M2 — Real-data world model

Completed engineering:
- direct MLP dynamics baseline;
- recurrent dynamics baseline;
- JEPA-style target-representation model;
- probe/calibration/rollout metrics;
- multi-seed benchmark matrix.

Remaining:
- bounded real-data ingestion;
- episode-level held-out evaluation;
- publish the first real-data result table.

## M3 — Planning

Implemented:
- random shooting;
- CEM;
- receding-horizon execution;
- ensemble uncertainty penalty;
- broken-dynamics negative control.

Remaining:
- equal-compute real-data/agent comparison.

## M4 — Frontier action models

Only after M3:
- latent-action discovery;
- vector-quantized skills;
- autoregressive proposal baseline;
- discrete diffusion proposal;
- equal-search-budget comparison.

## M5 — Self-play league

Only after a stable agent:
- historical checkpoints;
- exploiters/counter-policies;
- prioritized matchmaking;
- fixed maps/opponents;
- confidence intervals;
- diversity/exploitability reporting.
