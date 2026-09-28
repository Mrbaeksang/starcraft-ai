# Maintainers

## Project maintainer

- Sanghyeon Baek (@Mrbaeksang)

## Maintainer responsibilities

- protect the reproducibility contract;
- review research claims against available evidence;
- keep copyrighted StarCraft assets out of the repository;
- maintain non-cheating evaluation boundaries;
- require simpler baselines and negative controls for new methods;
- keep CI and security checks healthy.

## Decision process

Small engineering decisions may be merged when CI passes.

Research-method changes should document:

1. hypothesis;
2. baseline;
3. data/split;
4. metric;
5. compute budget;
6. failure mode;
7. reproduction command.

Architecture decisions that change the project’s core assumptions should be recorded in `docs/adr/`.
