# Current replay acquisition

## Important distinction: official pro matches vs current high-MMR ladder

Current Korean professional tournament replays are not generally published as freely downloadable packs. Liquipedia notes that Korean professionals are usually restricted from sharing replays because they expose strategy. RepMastered also protects automatically imported recent replays from download for a default 240-day period.

Therefore this repository does **not** pretend that an arbitrary current ladder replay is an official Proleague replay.

Instead we use two tracks:

1. **Provenance-clear real pro fixture** — `tests/fixtures/larva_vs_mini.rep` from the MIT-licensed `broodwar-live/bw-engine` repository, for parser/schema regression.
2. **Current-distribution snapshot** — recent 2400+ MMR ladder replays from the public CWAL Replay Vault on the current competitive map pool.

The second track is much more useful for keeping the model current while official tournament replay files are unavailable.

### GitHub Actions acquisition

`.github/workflows/replay-snapshot.yml` runs weekly and can also be launched manually.

It:

- reads the current map pool manifest;
- resolves those map names against CWAL's live replay vault;
- queries all six 1v1 matchup classes in the 2400–2900 MMR bucket;
- downloads a bounded number of recent raw `.rep` files;
- computes SHA-256 checksums;
- uploads the snapshot and manifest as a short-lived GitHub Actions artifact.

Raw CWAL files are **not auto-committed** because availability for download is not the same thing as an explicit redistribution license.

The resulting artifact can later be converted into `TransitionV1` records by the M1 collector/data pipeline.
