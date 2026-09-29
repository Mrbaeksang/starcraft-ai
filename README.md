# StarCraft AI

<p align="center">
  <strong>World model first. Agent second.</strong><br/>
  Open research on structured latent world models, planning, and self-improving agents for StarCraft: Brood War.
</p>

<p align="center">
  <a href="https://github.com/Mrbaeksang/starcraft-ai/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Mrbaeksang/starcraft-ai/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/Mrbaeksang/starcraft-ai/actions/workflows/nightly.yml"><img alt="Nightly" src="https://github.com/Mrbaeksang/starcraft-ai/actions/workflows/nightly.yml/badge.svg"></a>
  <a href="https://github.com/Mrbaeksang/starcraft-ai/actions/workflows/codeql.yml"><img alt="CodeQL" src="https://github.com/Mrbaeksang/starcraft-ai/actions/workflows/codeql.yml/badge.svg"></a>
  <a href="https://github.com/Mrbaeksang/starcraft-ai/releases"><img alt="Release" src="https://img.shields.io/github/v/release/Mrbaeksang/starcraft-ai?include_prereleases"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="PyTorch" src="https://img.shields.io/badge/PyTorch-2.14+-EE4C2C?logo=pytorch&logoColor=white">
  <a href="LICENSE"><img alt="MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <img alt="Status" src="https://img.shields.io/badge/status-experimental-orange">
</p>

> [!IMPORTANT]
> **Current status: M0 complete, M1 in progress.** This repository contains a reproducible research scaffold, real replay acquisition, model smoke tests, and CI research infrastructure. It does **not** yet contain a trained competitive StarCraft agent.

**Delivery target:** an agent that plays humans on the current StarCraft:
Remastered Battle.net public matchmaking and ladder. Background window capture
and a targeted keyboard input have been verified; mouse gameplay control and
the full live loop have not. See the [runtime probe](docs/REMASTERED_RUNTIME.md)
and [runtime gate](ROADMAP.md#runtime-gate--before-claiming-a-playable-agent).

## The idea

Most game agents are trained primarily to answer:

```text
What action should I take in this state?
```

This project asks a complementary question:

```text
If I take this action, what happens next?
```

The long-term agent should learn a compact internal model of Brood War, imagine candidate futures, and use those imagined futures for planning.

```text
structured observation
        ↓
entity encoder + memory
        ↓
latent world model
        ↓
imagined futures
        ↓
planner / policy
        ↓
structured game action
```

## Why this repository is different

- **Structured research data.** BWAPI/replay tooling exposes units, resources, orders, map data, and actions for offline research. The current Battle.net client still needs a verified player-observable live interface.
- **World-model-first research.** We compare mature model-based RL baselines with JEPA-style predictive representation learning.
- **Current data pipeline.** A weekly GitHub Actions job fetches bounded high-MMR replay snapshots on current competitive maps.
- **Falsifiable milestones.** Complex methods do not advance until simpler baselines pass measurable gates.
- **CI-first research.** CPU baselines, multi-seed checks, data validation, package builds, security scanning, and dependency maintenance run on GitHub Actions.

## Current roadmap

The [current-client runtime gate](ROADMAP.md#runtime-gate--before-claiming-a-playable-agent)
must be passed before this project can claim human public-match or ladder play.

| Milestone | Goal | Status |
|---|---|---|
| M0 | PyTorch project, reproducibility, synthetic latent-dynamics tests | ✅ complete |
| M1 | Versioned replay/state/action dataset and headless extraction | 🚧 current |
| M2 | Real-data world-model baselines and predictive representation | planned |
| M3 | Latent planning and negative controls | planned |
| M4 | Latent skills and discrete diffusion action proposals | research |
| M5 | Self-play population and fixed evaluation league | research |

See [ROADMAP.md](ROADMAP.md) and the open [GitHub Issues](https://github.com/Mrbaeksang/starcraft-ai/issues).

## Data pipeline

```text
StarData / public replays / current high-MMR snapshots
                         ↓
                    replay parser
                         ↓
             headless game-state reconstruction
                         ↓
          observation_t + action_t + observation_t+1
                         ↓
                 versioned TransitionV1
                         ↓
                Parquet / dataset loader
                         ↓
                     PyTorch tensors
                         ↓
                 world-model training
```

The repository already contains:

- a provenance-traceable real replay fixture;
- a weekly current high-MMR CWAL replay snapshot workflow;
- a pinned first 2026 snapshot manifest with match IDs and SHA-256 hashes;
- current competitive map metadata;
- historical StarData metadata.

Read [docs/CURRENT_REPLAYS.md](docs/CURRENT_REPLAYS.md) and [DATA_CARD.md](DATA_CARD.md).

## Model direction

The first real comparison will not assume that the newest method wins.

```text
simple supervised dynamics
          ↓
Dreamer/RSSM-style baseline
          vs
structured JEPA-style latent dynamics
          ↓
short-horizon latent planning
          ↓
only then: latent actions / diffusion proposals / league self-play
```

See [MODEL_CARD.md](MODEL_CARD.md), [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md), and [docs/REFERENCES.md](docs/REFERENCES.md).

## Quick start

Target development environment:

```text
Windows 11 host                         WSL2 Ubuntu
-------------------------------         ------------------------------
StarCraft / game data                   Python 3.12
optional BWAPI runtime          --->    PyTorch + CUDA
local replay extraction                 datasets / training / eval
```

Clone and install:

```bash
git clone https://github.com/Mrbaeksang/starcraft-ai.git
cd starcraft-ai

curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv sync --locked --extra cu130 --group dev
```

Verify an RTX machine:

```bash
uv run --extra cu130 scai doctor
uv run --extra cu130 scai smoke-train --steps 100 --device cuda
make EXTRA=cu130 check
```

CPU-only:

```bash
uv sync --locked --extra cpu --group dev
make EXTRA=cpu check
```

## CI-first research

Every push / pull request runs:

- Ruff lint + formatting;
- Python compilation;
- pytest;
- package build;
- model smoke training with multiple seeds.

Scheduled automation also runs:

- nightly model-size × seed CPU research matrix;
- weekly current high-MMR replay acquisition;
- CodeQL security analysis;
- Dependabot updates.

GitHub-hosted CPU runners are intentionally used for everything that does not require a licensed StarCraft installation or long GPU training. See [docs/CI_STRATEGY.md](docs/CI_STRATEGY.md).

## Repository map

```text
.
├── src/starcraft_ai/         # model, training, CLI
├── collector/                # replay/runtime integration boundary
├── data/sources/             # provenance + source manifests
├── data/snapshots/           # pinned replay identities/checksums
├── tests/                    # deterministic CI tests + real replay fixture
├── scripts/                  # acquisition / repository tooling
├── docs/                     # architecture and research protocol
├── site/                     # GitHub Pages landing page
├── MODEL_CARD.md
├── DATA_CARD.md
├── CHANGELOG.md
└── AGENTS.md                 # Codex/agent operating rules
```

## Research discipline

1. No benchmark without a reproducible command, seed, commit, and data manifest.
2. No “SOTA” or “human-level” claim without a directly comparable public protocol.
3. Non-cheating evaluation must preserve player-visible information boundaries.
4. Game binaries and commercial assets are never committed.
5. Every complex method must have a simpler baseline and a negative control.
6. A lower training loss alone is not evidence of a better game model.

Read [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## Contributing

Research, negative results, replay tooling, benchmarks, and infrastructure contributions are welcome.

- [Contributing guide](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)
- [Citation](CITATION.cff)
- [Changelog](CHANGELOG.md)

AI coding agents must read [AGENTS.md](AGENTS.md) first.

## Legal

StarCraft, StarCraft: Brood War, StarCraft: Remastered, Battle.net, and Blizzard Entertainment are trademarks of Blizzard Entertainment. This project is independent and is not affiliated with or endorsed by Blizzard Entertainment.
