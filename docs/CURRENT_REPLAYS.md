# Current replay acquisition

## Important distinction: official pro matches vs current high-MMR ladder

Current Korean professional tournament replays are not generally published as freely downloadable packs. Liquipedia notes that Korean professionals are usually restricted from sharing replays because they expose strategy. RepMastered also protects automatically imported recent replays from download for a default 240-day period.

Therefore this repository does **not** pretend that an arbitrary current ladder replay is an official Proleague replay.

Instead we use two tracks:

1. **Provenance-clear real pro fixture** — `tests/fixtures/larva_vs_mini.rep` from the MIT-licensed `broodwar-live/bw-engine` repository, for parser/schema regression.
2. **Current-distribution snapshot** — recent 2400+ MMR ladder replays from the public CWAL Replay Vault on the current competitive map pool.

The second track is useful for keeping the model current while official tournament replay files are unavailable.

## First live snapshot: verified

GitHub Actions run `36364494057` successfully downloaded and validated **12 raw replay files** from the 2400–2900 MMR bucket.

The bounded first snapshot contained games on:

- Colorless Fate
- Octagon SE
- Attitude SE
- Aiolos

The live vault also resolved the current map names for Backrooms, KnockOut, and Odyssey RE, but those maps did not appear in the final 12 newest selected games in this bounded run.

The exact match IDs, MMRs, byte sizes, and SHA-256 hashes are pinned in:

`data/snapshots/cwal-2026-09-28-2400plus.json`

This means the experiment can identify exactly which external replay files were used even after the short-lived Actions artifact expires.

## GitHub Actions acquisition

`.github/workflows/replay-snapshot.yml` runs weekly and can also be launched manually.

It:

- reads the current map pool manifest;
- resolves those map names against CWAL's live replay vault;
- queries all six 1v1 matchup classes in the 2400–2900 MMR bucket;
- downloads a bounded number of recent raw `.rep` files;
- computes SHA-256 checksums;
- validates the files;
- uploads the snapshot and manifest as a short-lived GitHub Actions artifact.

Raw CWAL files are **not auto-committed** because availability for download is not the same thing as an explicit redistribution license.

The resulting replay snapshot will later be converted into `TransitionV1` records by the M1 collector/data pipeline.
