# Reproducibility protocol

A public research result is incomplete unless another person can identify the exact code, data, configuration, and evaluation protocol used.

## Required experiment metadata

Every serious experiment must record:

- git commit SHA;
- model/config name;
- dataset manifest and hashes;
- split definition;
- random seed(s);
- observability mode;
- Python version;
- PyTorch/CUDA versions;
- hardware;
- parameter count;
- optimization steps;
- environment/replay transitions consumed;
- wall-clock time;
- peak memory;
- evaluation command;
- metric definitions.

## Comparison rules

When comparing methods, keep fixed where possible:

- train/validation/test data;
- interaction/data budget;
- parameter budget;
- optimizer budget;
- planning/search budget;
- seed set.

If any budget differs, report the difference explicitly.

## Seed policy

Smoke tests may use two seeds.

Research claims should normally use at least three seeds; more are preferred when variance is high.

## Negative controls

World-model planning experiments must include at least one deliberately broken control, such as shuffled or invalid dynamics. If a planner performs equally well with broken dynamics, the world model has not demonstrated useful predictive structure.

## Dataset leakage

Never split neighboring frames from the same game across train and held-out test.

Non-cheating evaluation must audit hidden enemy state and future-derived features.

## Artifact policy

GitHub Actions artifacts are temporary experiment outputs, not canonical dataset storage.

Persistent public claims should point to small versioned manifests, hashes, configs, and result tables committed to the repository.
