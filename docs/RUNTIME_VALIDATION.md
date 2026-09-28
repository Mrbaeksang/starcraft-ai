# Runtime extraction validation

M1-C is the final bridge from compile-tested infrastructure to a trustworthy real-game dataset.

## Automated checks already available

The Python audit tooling validates:

- strict TransitionV1 parsing;
- contiguous transition steps within each episode;
- monotonic observation frames;
- canonical dataset SHA-256;
- hidden enemy records are last-seen memory only;
- deterministic episode-level train/validation/test assignment;
- malformed JSONL failures include source line context;
- loader throughput in transitions/sec.

Commands:

    uv run --extra cpu scai audit-data data.jsonl
    uv run --extra cpu scai benchmark-data data.jsonl
    uv run --extra cpu scai compare-extractions run-a.jsonl run-b.jsonl
    uv run --extra cpu scai split-data data.jsonl splits.json

## One remaining licensed-runtime gate

GitHub Actions cannot ship or execute Blizzard's StarCraft installation.

Before M1-C can be declared complete, run one known replay twice through the local runtime extractor and compare the outputs:

    BWAPICollector.exe --mode replay --observability privileged --player-id 0 --output run-a.jsonl
    BWAPICollector.exe --mode replay --observability privileged --player-id 0 --output run-b.jsonl
    uv run --extra cpu scai compare-extractions run-a.jsonl run-b.jsonl

For the non-cheating training track, a player-observable replay reconstruction must additionally demonstrate that hidden enemy current positions are unavailable. The current BWAPI collector deliberately refuses player-observable replay mode rather than pretending the observer view is safe.

The preferred next implementation is a headless replay reconstruction path using licensed local StarCraft game-data files, followed by the same TransitionV1 audit.

## Definition of pass

M1-C can close only when:

1. the same replay produces the same canonical hash twice;
2. player-observable extraction passes the hidden-enemy audit;
3. a real replay has an episode-level split assignment;
4. loader throughput is recorded;
5. the commands and hashes are attached to issue #9.

Synthetic/self-test success alone is not sufficient.
