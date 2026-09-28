# Backend validation certificates

This directory stores **small verification certificates**, not replay data.

A certificate proves that one specific replay was extracted through:

1. the authoritative BWAPI 4.4.0 player-view reference path;
2. a specific headless backend commit;

and that the strict backend-comparison promotion policy passed.

## Why store a certificate?

Raw StarCraft runtime files and many replay files should not be committed.

The certificate instead pins:

- replay SHA-256;
- BWAPI TransitionV1 file SHA-256;
- headless TransitionV1 file SHA-256;
- exact headless backend git commit;
- comparison policy;
- all comparison metrics;
- a deterministic certificate id.

## Generate

```bash
uv run --extra cpu scai certify-backend \
  reference.jsonl \
  headless.jsonl \
  --replay-sha256 <SHA256_OF_REPLAY> \
  --candidate-backend broodwar-live/bw-engine \
  --candidate-backend-commit <40_CHAR_SHA> \
  --output data/certifications/<name>.json
```

The command refuses to write a certificate unless the strict promotion gate passes.

## CI

Every committed `*.json` certificate is revalidated by pytest.

Editing metrics by hand invalidates the deterministic certificate id or the promotion-policy checks.
