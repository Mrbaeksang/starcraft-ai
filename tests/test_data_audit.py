import json
from pathlib import Path

import pytest

from starcraft_ai.data.audit import (
    audit_jsonl,
    benchmark_loader,
    compare_extractions,
    episode_split,
)

FIXTURE = Path("tests/fixtures/transitions_v1.jsonl")


def test_fixture_passes_data_audit() -> None:
    result = audit_jsonl(FIXTURE)

    assert result.transitions == 2
    assert result.episodes == 1
    assert result.visible_enemy_records > 0
    assert result.hidden_enemy_memory_records > 0
    assert result.min_frame == 0
    assert result.max_frame == 16


def test_same_extraction_has_same_canonical_hash() -> None:
    identical, first, second = compare_extractions(FIXTURE, FIXTURE)

    assert identical
    assert first.canonical_sha256 == second.canonical_sha256


def test_episode_split_is_deterministic_and_episode_level() -> None:
    episode_ids = [f"episode-{index}" for index in range(100)]
    first = episode_split(episode_ids, seed=17)
    second = episode_split(list(reversed(episode_ids)), seed=17)

    assert first == second
    assert set(first) == set(episode_ids)
    assert {"train", "validation", "test"}.issubset(set(first.values()))


def test_malformed_json_reports_source_line(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text('{"schema_version":1}\nnot-json\n', encoding="utf-8")

    with pytest.raises(ValueError, match=r"broken\.jsonl:1|broken\.jsonl:2"):
        audit_jsonl(path)


def test_loader_benchmark_reports_positive_throughput() -> None:
    result = benchmark_loader(FIXTURE, repeats=2)

    assert result.transitions == 2
    assert result.elapsed_seconds > 0
    assert result.transitions_per_second > 0


def test_split_manifest_can_be_serialized() -> None:
    assignments = episode_split(["a", "b", "c"], seed=1)
    assert json.loads(json.dumps(assignments)) == assignments
