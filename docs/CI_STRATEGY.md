# CI-first research strategy

The public repository should do every task that does not require a licensed StarCraft installation or a real GPU.

## What GitHub Actions should own

### Every pull request / push

- lint and formatting;
- Python compilation;
- unit tests;
- package build;
- deterministic model smoke tests on multiple seeds;
- source/data-manifest tests;
- CodeQL for Python and GitHub Actions.

### Every night

Run a small matrix across:

- model sizes;
- random seeds.

The nightly matrix is not intended to train a useful StarCraft agent. Its job is to detect:

- numerical instability;
- accidental model slowdowns;
- parameter-count changes;
- loss regressions;
- seed-specific failures.

Results are tiny JSON artifacts retained for 7 days and a readable GitHub Job Summary.

### Manual GitHub UI experiment

`Manual CPU research run` lets a maintainer launch bounded CPU experiments without cloning the repository.

It intentionally:

- checks out `main`, not arbitrary PR code;
- accepts only a bounded step count;
- fans out four seeds to parallel standard runners;
- stores only small metric JSON files.

### Dependency reproducibility

`Sync uv lockfile` runs only after trusted pushes to `main` that modify dependency configuration.

It resolves `uv.lock` in GitHub Actions and commits the lockfile with `github-actions[bot]`, eliminating a local lockfile-maintenance step. It is never triggered by pull-request code.

Dependabot separately proposes `uv` and GitHub Actions upgrades.

## What GitHub-hosted CI cannot replace

Standard public runners currently provide 4 CPU cores, 16 GB RAM and 14 GB SSD, but no free GPU. A single hosted job can run for at most 6 hours.

Therefore GitHub-hosted Actions are suitable for:

- engineering;
- tests;
- CPU baselines;
- small ablations;
- data schema validation;
- reproducibility;
- packaging;
- security scanning.

They are not the right place for:

- multi-day RTX training;
- the full 365 GB StarData corpus;
- StarCraft/BWAPI runtime evaluation requiring a local licensed game installation.

## Storage discipline

Do not use Actions artifacts as a dataset store.

- Keep artifacts to small metrics/reports.
- Use short retention periods.
- GitHub Actions cache is for dependencies and disposable derived files, not canonical datasets.
- Canonical datasets need a versioned external object-store manifest when M1/M2 reaches that scale.

GitHub currently documents a 10 GB cache limit per repository, with caches unused for more than 7 days eligible for removal.

## GPU automation

Do **not** connect the developer workstation as a normal self-hosted runner to this public repository.

GitHub explicitly warns that public-repository self-hosted runners can execute untrusted code from malicious pull requests and can be persistently compromised.

If GPU automation is added later, use one of these patterns:

1. an isolated, disposable GPU runner with no personal files or credentials;
2. a separate private training-control repository that dispatches trusted commits from this public research repository;
3. a cloud GPU job launched from a protected environment after commit/review checks.

The public repository can still publish configs, commit SHAs, dataset hashes, and final metrics.

## CI gates by milestone

| Milestone | Required CI evidence |
|---|---|
| M0 | unit tests + finite gradients + deterministic synthetic benchmark |
| M1 | schema tests + fixture loader + leakage checks + collector compile |
| M2 | fixture training + held-out metric code + baseline comparisons |
| M3 | planner unit tests + broken-dynamics control |
| M4 | proposal-policy baseline/ablation tests |
| M5 | deterministic league scheduler + evaluation protocol tests |

The CI gate should become stricter as each milestone lands; future code should not be allowed to bypass an earlier gate.
