# Data policy

No real game assets or private replay collections are stored in Git.

Local layout:

```text
data/
├── raw/        # ignored
├── interim/    # ignored
└── processed/  # ignored
```

Small synthetic test fixtures may be committed under `tests/fixtures/`.

Every generated dataset version should have a manifest with schema version, runtime version, extraction commit, episode/transition counts, observability mode, split policy, and content hashes.
