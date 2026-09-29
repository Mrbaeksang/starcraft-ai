# Roadmap

The roadmap is gated by evidence, not dates.

## Product target — current Battle.net human matchmaking

The agent must eventually play human opponents through the current StarCraft:
Remastered Battle.net public matchmaking and ladder. A private lobby, legacy
1.16.1/BWAPI match, replay-only evaluation, or self-play does not satisfy this
target.

### Runtime gate — before claiming a playable agent

1. On the installed current Windows client, capture an unobscured game frame
   and deliver a harmless input; record the client version and evidence.
2. Build a player-observable screen-to-action loop that can identify the match
   state, select units, and issue commands at a measured latency. Keep the
   replay/BWAPI data path as research input until its observations and actions
   have been mapped to this live interface.
3. Complete a local game through that loop, then a human public match, then a
   ladder match. Record the client version, result, command evidence, and
   failures for each gate. Do not mark the ladder target complete before an
   actual ladder match finishes with the agent controlling the game.

The installed client was identified as 1.23.10.13515. Background window
capture and a harmless targeted keyboard input have been verified in the
[runtime probe](docs/REMASTERED_RUNTIME.md). Mouse targeting and gameplay
commands remain open, so no public-match runtime or playable agent is claimed.
Track progress in [issue #22](https://github.com/Mrbaeksang/starcraft-ai/issues/22).

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
