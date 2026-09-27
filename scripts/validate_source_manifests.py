from __future__ import annotations

import json
from pathlib import Path


REQUIRED_MAPS = {
    "KnockOut",
    "Odyssey RE",
    "Aiolos",
    "Octagon SE",
    "Backrooms",
    "Colorless Fate",
    "Attitude SE",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    source_dir = Path("data/sources")
    paths = sorted(source_dir.glob("*.json"))
    if not paths:
        raise SystemExit("no source manifests found")

    for path in paths:
        payload = load_json(path)
        if payload.get("schema_version") != 1:
            raise SystemExit(f"{path}: unsupported schema_version")
        if not payload.get("kind"):
            raise SystemExit(f"{path}: missing kind")

    map_pool = load_json(source_dir / "major_proleague_2026-07-30.json")
    maps = set(map_pool.get("maps", []))
    if maps != REQUIRED_MAPS:
        missing = sorted(REQUIRED_MAPS - maps)
        extra = sorted(maps - REQUIRED_MAPS)
        raise SystemExit(f"map pool mismatch; missing={missing} extra={extra}")

    video_index = load_json(source_dir / "youtube_seed_index.json")
    if video_index["policy"]["media_committed_to_repository"]:
        raise SystemExit("third-party media must not be committed")
    for item in video_index.get("videos", []):
        if not str(item.get("url", "")).startswith("https://www.youtube.com/watch?"):
            raise SystemExit(f"unexpected video URL: {item}")

    print(f"validated {len(paths)} source manifests")


if __name__ == "__main__":
    main()
