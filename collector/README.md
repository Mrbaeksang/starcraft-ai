# Collector

Boundary between the legacy Brood War runtime and the Python learner.

## M1 target

A Windows-side BWAPI client/collector that:

1. opens a replay or live match through BWAPI;
2. emits only fields allowed by the observability mode;
3. converts frames into a versioned transition format;
4. writes shards atomically;
5. reports extraction throughput and errors.

The learner must not import the collector directly.

## Why a separate process?

- BWAPI targets the classic Win32 runtime.
- PyTorch training is easier in WSL2/Linux.
- Collector failures stay isolated.
- Replay extraction and training can run independently.
- The data contract becomes testable and backend-independent.

Do not commit StarCraft binaries, MPQ archives, private replays, or copied Blizzard assets.
