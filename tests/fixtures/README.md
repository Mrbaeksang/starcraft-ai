# Replay fixtures

## larva_vs_mini.rep

A real Brood War replay used only as a parser/data-contract regression fixture.

Provenance:

- upstream repository: `broodwar-live/bw-engine`
- upstream commit: `befa5432c8749cdea196703c5b82c0f0fcfad2c5`
- upstream path: `tests/fixtures/larva_vs_mini.rep`
- upstream Git blob: `2a211635a334cbeeae65abdc56af715d7ade8313`
- upstream project license: MIT
- players represented by the upstream fixture name: Larva vs Mini

This fixture is **not** presented as a current 2026 replay. It exists so the project has one real, redistribution-traceable pro replay available in CI while the current-data pipeline uses short-lived external replay snapshots.

Current 2026 high-skill data is fetched from CWAL by `.github/workflows/replay-snapshot.yml`.
