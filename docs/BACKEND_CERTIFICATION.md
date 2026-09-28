# Backend certification

Backend comparison answers:

> Does this headless extraction match BWAPI closely enough on this replay?

Certification turns a passing comparison into a small, versioned artifact that the repository can retain.

## Certificate contents

```text
replay SHA-256
BWAPI reference JSONL SHA-256
headless JSONL SHA-256
candidate backend + exact commit
comparison thresholds
comparison metrics
deterministic certificate id
```

A certificate does not redistribute the replay or StarCraft files.

## Trust boundary

A certificate is evidence tied to exact hashes. It is not a cryptographic attestation that the local BWAPI run was honest.

For public research, keep:

- the exact extraction commands;
- BWAPI version;
- replay provenance;
- certificate;
- git commit of this repository.

## Promotion model

One passing replay is the M1-C minimum engineering gate.

Before large-scale scientific claims, repeat certification over multiple:

- maps;
- races/matchups;
- game phases;
- action types.

A later milestone can define a broader backend-validation suite without changing the certificate schema.
