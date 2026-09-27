# StarCraft AI

[![CI](https://github.com/Mrbaeksang/starcraft-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Mrbaeksang/starcraft-ai/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.14+-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Status](https://img.shields.io/badge/status-experimental-orange)
[![GitHub stars](https://img.shields.io/github/stars/Mrbaeksang/starcraft-ai?style=social)](https://github.com/Mrbaeksang/starcraft-ai)

> **World model first. Agent second.**
>
> Open research on a StarCraft: Brood War agent that learns a structured latent world model, imagines future trajectories, and eventually plans and self-improves under partial observability.

This is intentionally **not** a scripted build-order bot and **not** a state-of-the-art claim. The project is built in public with measurable milestones and a target of reproducible experiments on one high-end consumer GPU.

## Research hypothesis

Most Brood War bots execute rules or directly learn a policy:

```text
observation -> policy -> action
```

This project investigates:

```text
observation -> entity encoder -> latent world model -> imagined futures
                    |                       |
                    |                       v
                    |             reward / terminal /
                    |             uncertainty prediction
                    |                       |
                    +-----------------------+
                                    |
                                    v
                              planner / policy
                                    |
                                    v
                                  action
```

Long-term targets:

- **structured entity encoder** instead of RGB video generation;
- **action-conditioned latent world model** with a JEPA-style target representation;
- **latent planning** before expensive real environment interaction;
- learned **latent skills/actions** rather than hand-defining every strategic concept;
- experimental **discrete diffusion policy** as a proposal model for combinatorial actions;
- eventually, adversarial and league-style self-play.

A method only advances when the previous milestone passes measurable tests.

## Why Brood War?

- BWAPI exposes structured units, resources, orders, terrain, and replay data.
- Live bots can be restricted to visible information, preserving partial observability.
- Replays can be analyzed frame-by-frame.
- The action space mixes economy, production, positioning, micro, and long-horizon strategy.
- Structured state lets us test world-model ideas without wasting most compute reconstructing pixels.

BWAPI targets classic StarCraft: Brood War 1.16.1. Game binaries and copyrighted assets are **never** distributed by this repository.

## Data strategy

The project separates **what is useful for learning** from **what is merely available online**.

| Layer | Source | Role |
|---|---|---|
| Historical structured pretraining | StarData (65,646 games reported upstream) | learn broad Brood War dynamics and representations |
| Current competitive distribution | recent Proleague map pools + public match metadata | decide what maps, players, matchups, and strategies need coverage |
| Canonical control labels | our own BWAPI replay/live collector | exact observations/actions used for training and evaluation |
| Broadcast video | SOOP/YouTube metadata and authorized local media only | strategy discovery, qualitative analysis, optional vision experiments |

A recent Major Proleague event (2026-09-17) used **Backrooms, Octagon SE, KnockOut, Colorless Fate, Odyssey RE, Attitude SE, and Aiolos**. The repository tracks that pool as a current-distribution seed without redistributing the map files themselves.

Public broadcast videos are **not copied into Git**. We keep URLs and factual metadata, then build local-only indexes when needed. This avoids turning a world-model project into a fragile video-scraping/OCR project and keeps the canonical learning labels tied to BWAPI state.

See [Data acquisition](docs/DATA_ACQUISITION.md).

## CI-first development

This public repository deliberately pushes as much work as possible into GitHub Actions.

- **Every push / PR:** lint, formatting, compile checks, tests, package build, and two-seed model smoke tests.
- **Nightly:** 8-way CPU research matrix across model sizes and seeds.
- **Manual from GitHub UI:** bounded 4-seed CPU experiment without cloning the repository.
- **Security:** CodeQL scans both Python and GitHub Actions workflows.
- **Dependencies:** Dependabot maintains both `uv` and GitHub Actions dependencies.
- **Artifacts:** only tiny metric JSON files are retained; datasets/checkpoints are not abused as Actions storage.

Standard GitHub-hosted runners for public repositories are useful for engineering, small baselines, and reproducibility, but they do not provide a free GPU. The only planned local responsibilities are therefore the things CI genuinely cannot provide: the licensed Brood War/BWAPI runtime and long RTX training.

See [CI strategy](docs/CI_STRATEGY.md), [reference map](docs/REFERENCES.md), and the canonical [TODO](TODO.md).

## Current status

| Milestone | Goal | Status |
|---|---|---|
| M0 | Reproducible PyTorch project + synthetic latent-dynamics smoke test | **implemented** |
| M1 | BWAPI replay/state collector and versioned transition schema | next |
| M2 | Real replay dataset + JEPA-style latent world model | planned |
| M3 | Latent rollout evaluation + planning baseline | planned |
| M4 | Learned latent skills + diffusion proposal policy ablation | research |
| M5 | Self-play population / league evaluation | research |

**M0 is infrastructure, not a trained StarCraft agent.**

## Quick start — RTX 5090 / WSL2

Recommended split:

```text
Windows 11 host                         WSL2 Ubuntu
-------------------------------         ------------------------------
StarCraft: Brood War 1.16.1             Python 3.12
BWAPI 4.4.0 / collector        --->     PyTorch + CUDA
replays / live state                     datasets / training / eval
```

### Clone

```bash
git clone https://github.com/Mrbaeksang/starcraft-ai.git
cd starcraft-ai
```

### Install

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv sync --locked --extra cu130 --group dev
```

CPU-only / CI:

```bash
uv sync --locked --extra cpu --group dev
```

### Verify

```bash
uv run --extra cu130 scai doctor
uv run --extra cu130 scai smoke-train --steps 100 --device cuda
make EXTRA=cu130 check
```

See [Local setup](docs/LOCAL_SETUP.md) for the Windows/BWAPI side.

## What is being learned?

```text
entities_t --------> online entity encoder ----> z_t --------+
                                                             |
action type + args -> action encoder ----------> a_t --------+--> predictor --> zhat_(t+1)
                                                                                 |
entities_(t+1) ---> EMA target encoder -----------------------> z_(t+1) ----------+
```

Auxiliary heads predict immediate reward and terminal probability.

A useful world model must do more than minimize training loss. M2 requires held-out temporal prediction, representation probes, calibration, and downstream planning gains.

## Repository layout

```text
.
├── AGENTS.md                 # persistent Codex/agent instructions
├── collector/                # BWAPI runtime integration boundary
├── data/                     # local dataset policy; no game assets
├── docs/
│   ├── ARCHITECTURE.md
│   ├── LOCAL_SETUP.md
│   └── RESEARCH_PLAN.md
├── src/starcraft_ai/
│   ├── cli.py
│   ├── synthetic.py
│   ├── training.py
│   └── models/world_model.py
├── tests/
├── pyproject.toml
└── Makefile
```

## Development

```bash
make EXTRA=cpu check
make EXTRA=cu130 check

uv run --extra cu130 scai doctor
uv run --extra cu130 scai smoke-train --steps 100 --device cuda
```

## Training-time expectations

| Stage | What success means | Planning estimate |
|---|---|---|
| M0 | code, CUDA, gradients, loss work | minutes |
| M1 | replay extraction pipeline validated | hours to days of engineering |
| M2-small | model learns on a bounded replay slice | hours |
| M2-useful | held-out metrics stabilize | 1–3 days |
| M3+ | repeated planning / self-play experiments | days to weeks |

These are engineering estimates, **not benchmark claims**. Environment throughput and dataset quality can dominate GPU speed.

## Research rules

1. No benchmark without a reproducible command and seed.
2. No “SOTA” claim without a directly comparable public protocol.
3. Live evaluation uses only information allowed by the configured BWAPI observation boundary.
4. Game binaries, commercial assets, and private replay dumps are not committed.
5. Every complex method gets a simpler baseline and an ablation.

Read [RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md) before changing the learning objective.

## References

- [BWAPI](https://github.com/bwapi/bwapi)
- [AlphaStar](https://deepmind.google/discover/blog/alphastar-mastering-the-real-time-strategy-game-starcraft-ii/)
- [DreamerV3](https://www.nature.com/articles/s41586-025-08744-2)
- [TD-MPC2](https://www.tdmpc2.com/)
- [V-JEPA 2](https://ai.meta.com/vjepa/)
- [uv + PyTorch](https://docs.astral.sh/uv/guides/integration/pytorch/)

These are research inspirations, not reproduced-results claims.

## Contributing

Experiments, infrastructure, replay tooling, evaluation ideas, and skeptical ablations are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md). AI coding agents should read [AGENTS.md](AGENTS.md) first.

## Legal

StarCraft, StarCraft: Brood War, StarCraft: Remastered, Battle.net, and Blizzard Entertainment are trademarks of Blizzard Entertainment. This is an independent research project and is not affiliated with or endorsed by Blizzard Entertainment.
