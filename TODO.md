# TODO / research execution order

This is the canonical execution order for humans and coding agents.

## Now — M1 data contract

- [ ] Define `EpisodeMetadataV1`, `ObservationV1`, `ActionV1`, `TransitionV1`.
- [ ] Add JSON/Parquet serialization with schema-version tests.
- [ ] Add a synthetic fixture that is legal to redistribute.
- [ ] Implement hidden-information/leakage tests.
- [ ] Implement Linux/WSL dataset loader and benchmark.
- [ ] Scaffold the Windows BWAPI collector.
- [ ] Add Windows compile-only CI for the collector.
- [ ] Extract one real replay locally and validate round-trip hashes.

## Next — M2 baseline suite

- [ ] Add a direct next-feature MLP baseline.
- [ ] Add a small recurrent/RSSM or Dreamer-style baseline.
- [ ] Add the structured EMA target-representation model.
- [ ] Define episode-level train/validation/test splitting.
- [ ] Add linear probes: economy, army, tech, map-control proxies.
- [ ] Add reward/terminal calibration.
- [ ] Add multi-step rollout degradation.
- [ ] Run all baseline configs across >=3 seeds in CI on fixtures.
- [ ] Run bounded real-data experiments and publish config/hash/metrics.

## Then — M3 planning

- [ ] Random-shooting planner.
- [ ] CEM-style planner.
- [ ] Uncertainty penalty.
- [ ] Broken/shuffled-dynamics negative control.
- [ ] Equal-compute no-planning baseline.

## Later — M4 frontier experiments

- [ ] Inverse-dynamics latent-action baseline.
- [ ] Vector-quantized skill discovery.
- [ ] Autoregressive proposal policy.
- [ ] Discrete diffusion proposal policy.
- [ ] Equal-search-budget comparison.

## Last — M5 self-play

- [ ] Historical checkpoint pool.
- [ ] Exploiter/counter-policy slots.
- [ ] Prioritized matchmaking.
- [ ] Fixed opponent/map evaluation suite.
- [ ] Confidence intervals and exploitability/diversity metrics.

## Automation

- [x] PR lint/test/build.
- [x] Multi-seed model smoke.
- [x] Nightly CPU matrix.
- [x] Manual GitHub UI CPU experiments.
- [x] CodeQL.
- [x] Dependabot for uv and GitHub Actions.
- [x] Automatic `uv.lock` synchronization on trusted main changes.
- [ ] Add benchmark regression thresholds after enough history exists.
- [ ] Add collector Windows CI when its build files exist.
- [ ] Add small legally redistributable M1 fixture to nightly training.
- [ ] Add automatic benchmark table generation from result JSON.
- [ ] Add release workflow only after the first reproducible real-data checkpoint.

## Explicitly not yet

- Full StarData download in GitHub Actions.
- Broadcast-video bulk download.
- Public-repository self-hosted runner on a personal workstation.
- “SOTA”, “human-level”, or Pluto-comparison claims without a common protocol.
