import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index public YouTube metadata without downloading media."
    )
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--yt-dlp",
        default="yt-dlp",
        help=(
            "yt-dlp executable path. Recommended stable version is documented "
            "in DATA_ACQUISITION.md."
        ),
    )
    return parser.parse_args()


def run_search(executable: str, query: str, limit: int) -> list[dict[str, Any]]:
    target = f"ytsearch{limit}:{query}"
    command = [
        executable,
        target,
        "--flat-playlist",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
    ]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    rows: list[dict[str, Any]] = []
    for entry in payload.get("entries") or []:
        if not entry:
            continue
        rows.append(
            {
                "id": entry.get("id"),
                "url": entry.get("webpage_url") or entry.get("url"),
                "title": entry.get("title"),
                "channel": entry.get("channel") or entry.get("uploader"),
                "channel_id": entry.get("channel_id") or entry.get("uploader_id"),
                "duration": entry.get("duration"),
                "timestamp": entry.get("timestamp"),
                "query": query,
            }
        )
    return rows


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("id") or row.get("url"))
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def main() -> None:
    args = parse_args()
    if args.limit < 1 or args.limit > 200:
        raise SystemExit("--limit must be between 1 and 200")

    rows: list[dict[str, Any]] = []
    for query in args.query:
        rows.extend(run_search(args.yt_dlp, query, args.limit))

    output = {
        "schema_version": 1,
        "kind": "external_video_metadata",
        "media_downloaded": False,
        "queries": args.query,
        "videos": dedupe(rows),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(output['videos'])} unique video records -> {args.output}")


if __name__ == "__main__":
    main()
