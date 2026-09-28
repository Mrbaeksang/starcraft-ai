# BWAPI collector

Windows-side external BWAPI client that emits the same TransitionV1 JSONL contract consumed by the Python learner.

## Modes

Live mode defaults to player-observable state. It does not enable BWAPI CompleteMapInformation and excludes enemy units not visible to the evaluated player.

    BWAPICollector.exe --mode live --observability player --output C:\\starcraft-ai-data\\live.jsonl

Replay mode currently supports privileged extraction only. Player-observable replay reconstruction remains the M1-C correctness gate.

    BWAPICollector.exe --mode replay --observability privileged --player-id 0 --output C:\\starcraft-ai-data\\replay.jsonl

## Transition timing

The collector watches Unit::getLastCommandFrame() / getLastCommand(). Supported command events create action records, then the state is observed again after --horizon-frames (default 8).

Unsupported command types are skipped rather than incorrectly coerced into the V1 action vocabulary.

## Atomic output

Output is written to <output>.tmp first and renamed only after the shard is complete.

## CI

GitHub-hosted runners do not contain StarCraft. The Windows workflow therefore:

1. checks out the official BWAPI 4.4.0 headers;
2. compiles the runtime collector translation unit as x86 C++17;
3. builds a contract self-test executable;
4. emits a TransitionV1 JSONL shard;
5. downloads that shard on Linux and validates it with scai inspect-data.

Actual game runtime validation is tracked separately in M1-C.
