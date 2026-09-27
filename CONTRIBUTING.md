# Contributing

Contributions are welcome, especially when they make an experiment easier to falsify, reproduce, or compare.

## Before opening a PR

```bash
uv sync --extra cpu --group dev
make EXTRA=cpu check
```

For CUDA-specific changes, also run the relevant GPU smoke test locally.

## Good contributions

- BWAPI replay/state extraction;
- versioned data schemas;
- dataset validation and leakage checks;
- representation probes;
- model-based planning baselines;
- profiling and throughput improvements;
- ablations and negative results;
- documentation that makes an experiment reproducible.

## Research-method PR template

A PR that changes a learning method should answer:

1. What is the hypothesis?
2. What is the simplest baseline?
3. Which dataset and split are used?
4. Which metric can falsify the hypothesis?
5. What is the expected failure mode?
6. What exact command reproduces the result?

## Code expectations

- Python 3.12.
- Type public functions.
- Keep CPU tests fast.
- Use explicit devices; do not hard-code CUDA.
- Keep new dependencies minimal.
- Run Ruff and pytest.
- Preserve partial observability for the non-cheating live track.
- Do not commit game binaries, commercial assets, or private replay dumps.

## Issues

Use the experiment issue form for research proposals. Small engineering fixes can use the bug/engineering form.

A useful issue has a bounded definition of done and a reproduction path.
