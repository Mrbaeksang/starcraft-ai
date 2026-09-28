#!/usr/bin/env bash
set -euo pipefail

REPLAY="${1:?usage: scripts/extract_replay.sh GAME.rep [OUTPUT_DIR]}"
OUTPUT_DIR="${2:-artifacts/local-extraction}"
ROOT="${STARCRAFT_DATA_ROOT:-}"

mkdir -p "$OUTPUT_DIR"

if [ -z "$ROOT" ]; then
  echo "STARCRAFT_DATA_ROOT is not set." >&2
  echo "Set it to the StarCraft directory containing arr/ and tileset/." >&2
  exit 2
fi

cargo run --release --manifest-path extractor/headless/Cargo.toml --   --replay "$REPLAY"   --output "$OUTPUT_DIR/transitions.jsonl"   --manifest "$OUTPUT_DIR/manifest.json"   --game-data-root "$ROOT"

uv run --extra cpu scai audit-data "$OUTPUT_DIR/transitions.jsonl"
uv run --extra cpu scai pack-data   "$OUTPUT_DIR/transitions.jsonl"   "$OUTPUT_DIR/transitions.npz"

echo "done: $OUTPUT_DIR"
