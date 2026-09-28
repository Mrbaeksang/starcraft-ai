from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_BASE = "https://api.aws.cwal.gg"
DEFAULT_MATCHUPS = ("ZvT", "ZvP", "TvP", "ZvZ", "TvT", "PvP")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a bounded snapshot of recent high-MMR CWAL replay-vault games."
    )
    parser.add_argument(
        "--map-manifest",
        type=Path,
        default=Path("data/sources/major_proleague_2026-09-17.json"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mmr-min", type=int, default=2400)
    parser.add_argument("--mmr-max", type=int, default=2900)
    parser.add_argument("--max-replays", type=int, default=12)
    parser.add_argument("--per-query", type=int, default=2)
    parser.add_argument("--request-delay", type=float, default=0.15)
    return parser.parse_args()


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "starcraft-ai-research/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "starcraft-ai-research/0.1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def normalize_map(value: str) -> str:
    value = value.lower()
    value = re.sub(r"^\(\d+\)", "", value)
    value = re.sub(r"\.(?:scx|scm)$", "", value)
    return re.sub(r"[^a-z0-9가-힣]+", "", value)


def resolve_map(requested: str, available: list[str]) -> str:
    needle = normalize_map(requested)
    candidates: list[tuple[int, int, str]] = []

    for name in available:
        normalized = normalize_map(name)
        score = 0
        if normalized == needle:
            score = 1000
        elif normalized.startswith(needle):
            score = 800
        elif needle in normalized:
            score = 600
        elif normalized in needle:
            score = 400

        if re.search(r"copy|복사본", name, re.IGNORECASE):
            score -= 100
        if name.lower().endswith(".scm"):
            score -= 5
        if score > 0:
            candidates.append((score, -len(name), name))

    if not candidates:
        raise RuntimeError(f'CWAL has no map matching "{requested}"')

    candidates.sort(reverse=True)
    return candidates[0][2]


def vault_page(map_file: str, matchup: str, mmr_min: int, mmr_max: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "matchup": matchup,
            "map": map_file,
            "limit": "100",
            "mmrLo": str(mmr_min),
            "mmrHi": str(mmr_max),
        }
    )
    payload = fetch_json(f"{API_BASE}/api/vault?{query}")
    replays = payload.get("replays")
    if not isinstance(replays, list):
        raise RuntimeError("CWAL returned an invalid replay-vault response")
    return [item for item in replays if isinstance(item, dict) and item.get("matchId")]


def main() -> None:
    args = parse_args()
    if not 800 <= args.mmr_min < args.mmr_max <= 2900:
        raise SystemExit("MMR bounds must satisfy 800 <= min < max <= 2900")
    if not 1 <= args.max_replays <= 100:
        raise SystemExit("--max-replays must be in [1, 100]")
    if not 1 <= args.per_query <= 10:
        raise SystemExit("--per-query must be in [1, 10]")

    map_manifest = json.loads(args.map_manifest.read_text(encoding="utf-8"))
    requested_maps = list(map_manifest["maps"])

    maps_payload = fetch_json(f"{API_BASE}/api/vault/maps")
    available_maps = maps_payload.get("maps")
    if not isinstance(available_maps, list):
        raise RuntimeError("CWAL returned an invalid map response")

    resolved_maps = {
        requested: resolve_map(requested, [str(item) for item in available_maps])
        for requested in requested_maps
    }

    candidates: dict[str, dict[str, Any]] = {}
    query_log: list[dict[str, Any]] = []

    for requested_map, map_file in resolved_maps.items():
        for matchup in DEFAULT_MATCHUPS:
            replays = vault_page(
                map_file=map_file,
                matchup=matchup,
                mmr_min=args.mmr_min,
                mmr_max=args.mmr_max,
            )
            selected = replays[: args.per_query]
            query_log.append(
                {
                    "requested_map": requested_map,
                    "cwal_map": map_file,
                    "matchup": matchup,
                    "returned": len(replays),
                    "selected": len(selected),
                }
            )
            for replay in selected:
                match_id = str(replay["matchId"])
                replay = dict(replay)
                replay["requestedMap"] = requested_map
                replay["cwalMap"] = map_file
                replay["vaultMatchup"] = matchup
                candidates.setdefault(match_id, replay)
            time.sleep(args.request_delay)

    ordered = sorted(
        candidates.values(),
        key=lambda item: float(item.get("timestamp") or 0),
        reverse=True,
    )[: args.max_replays]

    replay_dir = args.output_dir / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for replay in ordered:
        match_id = str(replay["matchId"])
        url = f"{API_BASE}/api/replay/{urllib.parse.quote(match_id, safe='')}/file"
        payload = fetch_bytes(url)
        if len(payload) < 1024:
            raise RuntimeError(f"replay {match_id} is unexpectedly small ({len(payload)} bytes)")

        path = replay_dir / f"{match_id}.rep"
        path.write_bytes(payload)
        records.append(
            {
                "match_id": match_id,
                "requested_map": replay.get("requestedMap"),
                "cwal_map": replay.get("cwalMap"),
                "matchup": replay.get("vaultMatchup"),
                "timestamp": replay.get("timestamp"),
                "duration": replay.get("duration"),
                "race": replay.get("race"),
                "opponent_race": replay.get("opponentRace"),
                "vault_mmr": replay.get("mmr"),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "source_url": url,
                "file": str(path.relative_to(args.output_dir)),
            }
        )
        time.sleep(args.request_delay)

    manifest = {
        "schema_version": 1,
        "kind": "cwal_high_mmr_replay_snapshot",
        "source": "https://cwal.gg/replays",
        "api_base": API_BASE,
        "mmr_min": args.mmr_min,
        "mmr_max": args.mmr_max,
        "requested_maps": requested_maps,
        "resolved_maps": resolved_maps,
        "matchups": list(DEFAULT_MATCHUPS),
        "queries": query_log,
        "replays": records,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"downloaded {len(records)} replay files -> {args.output_dir}")
    for record in records:
        print(
            f"{record['requested_map']}: {record['matchup']} "
            f"{record['match_id']} {record['bytes']} bytes"
        )


if __name__ == "__main__":
    main()
