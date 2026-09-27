import json
from pathlib import Path


def test_source_manifests_are_valid_json_v1() -> None:
    paths = sorted(Path("data/sources").glob("*.json"))
    assert paths

    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        assert payload["kind"]


def test_third_party_video_media_is_not_committed() -> None:
    payload = json.loads(
        Path("data/sources/youtube_seed_index.json").read_text(encoding="utf-8")
    )
    assert payload["policy"]["media_committed_to_repository"] is False
