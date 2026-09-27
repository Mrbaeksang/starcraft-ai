# Reference implementations and research map

This project separates **engineering references** from **research hypotheses**.

## Brood War engineering references

### BWAPI

Repository: https://github.com/bwapi/bwapi

Use for:

- game-state interface;
- non-cheating visibility semantics;
- replay analysis;
- unit/action definitions;
- Windows Brood War 1.16.1 integration.

Important property: BWAPI hides fog-of-war information from AI modules by default, which is the behavior our non-cheating evaluation track should preserve.

### TorchCraftAI / CherryPi

Repository: https://github.com/TorchCraft/TorchCraftAI

Use as an architectural reference for:

- complete-game Brood War agents;
- modular bot subsystems;
- reinforcement-learning minigames and training loops;
- TCP/BWAPI integration patterns;
- CherryPi, the SSCAIT 2017–18 winning bot.

Do not copy its architecture blindly. It is valuable precisely because it provides a strong historical complete-agent reference against which a world-model architecture can be contrasted.

### StarData

Repository: https://github.com/TorchCraft/StarData

Reported upstream:

- 65,646 games;
- 1.535 billion frames;
- 496 million player actions;
- 8 dumped frames/sec;
- about 365 GB compressed.

Use as a historical structured-data reference and possible bounded pretraining source. The upstream repository is archived and its replay/runtime distribution is old, so current-map evaluation must remain separate.

## World-model baselines

### DreamerV3

Paper: *Mastering diverse control tasks through world models*, Nature 2025.

Code: https://github.com/danijar/dreamerv3

Why it matters:

- mature, open-source world-model RL baseline;
- actor, critic, and world model trained from replayed experience;
- fixed-hyperparameter evaluation across many domains;
- strong reference for losses, normalization, replay ratio, and evaluation discipline.

Project rule: before claiming our JEPA-style dynamics are better, implement an appropriately scaled Dreamer-like/RSSM baseline or explain exactly why a direct comparison is invalid.

### TD-MPC2

Project: https://www.tdmpc2.com/

Why it matters:

- latent model-predictive control;
- strong reference for testing whether learned latent dynamics are actually useful for planning.

Project rule: M3 should begin with simple shooting/CEM and use TD-MPC2 as a design reference rather than jumping immediately to an exotic planner.

## Predictive representation research

### V-JEPA 2

Meta AI, 2025.

Why it matters:

- self-supervised prediction in representation space;
- explicit understanding/prediction/planning research;
- useful reference for avoiding unnecessary pixel reconstruction.

Caution: V-JEPA 2 is a video/physical-world system. Our structured Brood War encoder is an adaptation hypothesis, not a reproduction.

### AdaWorld

ICML 2025: *Learning Adaptable World Models with Latent Actions*.

Why it matters:

- self-supervised latent-action extraction;
- action-conditioned world modelling;
- relevant to the later M4 question of whether strategic skills can be discovered rather than manually named.

Caution: do not add latent-action machinery before the labelled-action M2 baseline is working.

### SWIRL

2026 preprint: *Self-Improving World Modelling with Latent Actions*.

Why it matters:

- forward/inverse world models treat actions as latent variables;
- useful as a frontier research reference for later self-improving skill discovery.

Caution: preprint evidence is weaker than a mature baseline and the reported domains are not Brood War.

## Combinatorial policy research

### Discrete diffusion policies

ICML 2026: *Reinforcement Learning with Discrete Diffusion Policies for Combinatorial Action-Spaces*.

Why it matters:

Brood War actions are naturally combinatorial: selected entities, command type, target entity/position, production/build choices, and potentially short plan sequences.

Project rule: only evaluate diffusion proposals in M4 after M3 demonstrates that planning with learned dynamics is useful. Compare against an autoregressive proposal under equal model/search budgets.

## Required order of evidence

```text
BWAPI data correctness
        ↓
simple supervised dynamics baseline
        ↓
Dreamer/RSSM-style baseline
        ↓
JEPA-style representation hypothesis
        ↓
simple latent planning
        ↓
latent-action discovery
        ↓
diffusion proposal policy
        ↓
self-play population
```

Newer is not automatically better. Each arrow is a CI/evaluation gate.
