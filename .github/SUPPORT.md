# Support

This is an experimental research repository, not a commercial StarCraft support project.

## Use GitHub Issues for

- reproducible bugs;
- data-format problems;
- replay/parser failures;
- benchmark/reproducibility issues;
- bounded research proposals.

## Use Discussions for

- architecture questions;
- paper/reference discussion;
- experiment interpretation;
- open-ended research ideas.

Before filing an issue, include the exact commit and the output of:

    uv run --extra cpu scai doctor

For CUDA issues use:

    uv run --extra cu130 scai doctor

Do not upload Blizzard game binaries, proprietary assets, credentials, or private replay collections to an issue.
