# v0.1.0 — Research Scaffold

The first public infrastructure release of StarCraft AI.

This release establishes the reproducible research environment before real-data world-model training begins.

## Included

- structured PyTorch world-model scaffold;
- deterministic CPU/CUDA smoke training;
- CI quality gates and nightly multi-seed research matrix;
- CodeQL and Dependabot;
- current competitive-map metadata;
- high-MMR replay acquisition and pinned replay manifests;
- provenance-traceable real replay fixture;
- research, architecture, benchmark, model-card, and data-card documentation.

## Research status

M0 is complete. M1 focuses on converting real replay execution into a versioned `ObservationV1 + ActionV1 -> ObservationV1` transition dataset.

There is no competitive gameplay checkpoint in this release.
