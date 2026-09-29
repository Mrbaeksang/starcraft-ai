# AGENTS.md

## Mission

Build a reproducible open research framework for a StarCraft: Brood War agent based on structured latent world models and planning. The delivery target is autonomous play against humans on the current Battle.net public matchmaking and ladder.

This repository values falsifiable experiments over hype. Do not claim an idea is stronger, novel, or state of the art unless the repository contains a directly supporting evaluation.

## Read first

Before changing learning/data architecture, read:

1. `ROADMAP.md` and the open GitHub Issues
2. `docs/RESEARCH_PLAN.md`
3. `docs/REFERENCES.md`
4. `docs/CI_STRATEGY.md`
5. `docs/DATA_ACQUISITION.md`

## Environment

- Primary learner: Windows 11 host + WSL2 Ubuntu.
- Python 3.12, package manager uv.
- GPU target: NVIDIA RTX 5090 via PyTorch CUDA 13.0 wheels.
- Offline collector: classic 1.16.1 + BWAPI on Windows. Live target: current StarCraft: Remastered client; see `docs/REMASTERED_RUNTIME.md`.
- Never commit StarCraft binaries, MPQ files, commercial assets, or private replay collections.

## CI-first rule

If a task can run on a standard GitHub-hosted CPU runner, implement it in CI instead of requiring a local manual step.

Every completed feature should leave behind an automated test, benchmark, or workflow where practical.

Do not use a developer workstation as a public-repository self-hosted runner.

## First commands

GPU:

```bash
uv sync --locked --extra cu130 --group dev
uv run --extra cu130 scai doctor
uv run --extra cu130 scai smoke-train --steps 100 --device cuda
make EXTRA=cu130 check
```

CPU / CI:

```bash
uv sync --locked --extra cpu --group dev
make EXTRA=cpu check
```

## Engineering rules

1. Follow `ROADMAP.md` milestone order and the open GitHub Issues.
2. Keep the Windows BWAPI runtime boundary separate from the WSL2 learner.
3. Prefer small typed PyTorch modules over a large RL framework until M2 is validated.
4. Every model change preserves or adds a deterministic CPU smoke/fixture test.
5. Every training command accepts a seed and logs its effective config.
6. Do not add a large dependency without explaining why NumPy/PyTorch/stdlib is insufficient.
7. Keep data schemas versioned and backward-readable where practical.
8. Avoid hidden privileged information in live-game observations.
9. Do not jump to M4/M5 before M1/M2/M3 gates pass.
10. Fix root causes; do not silence tests, lint rules, or negative controls.

## Research rules

- Separate representation quality, world-model prediction, planning quality, and game strength.
- Compare complex methods with simpler baselines.
- Use held-out replays/maps/players where generalization matters.
- Public benchmark claims include wall-clock time, environment steps, hardware, seeds, and uncertainty.
- Prefer ablations that can disprove the method.
- Do not use win rate alone to debug representation learning.
- “Recent” or “novel” methods do not replace a mature baseline.

## Code style

- Python 3.12 typing on public functions.
- Ruff is the formatter/linter authority.
- Tensor shape comments are encouraged at module boundaries.
- Device placement must be explicit; no direct `.cuda()` calls in library code.
- CI tests must remain fast on CPU.

## PRs

Research-method PRs state: hypothesis, baseline, dataset/split, metric, failure mode, and reproduction command.

## Immediate roadmap

Complete **M1 replay/state collection** and the current-client runtime gate before claiming a playable agent. Do not jump to diffusion or self-play.

M1 definition of done:

- versioned transition record;
- deterministic replay extraction on Windows;
- hidden-information leakage disabled by default;
- tiny legal/synthetic fixture;
- Linux/WSL2 loader tests;
- measured transitions/sec;
- compile/test paths automated in CI where possible.
