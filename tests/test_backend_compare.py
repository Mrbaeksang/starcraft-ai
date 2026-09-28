import json
from pathlib import Path

from starcraft_ai.data.backend_compare import BackendComparisonPolicy, compare_backends

FIXTURE = Path("tests/fixtures/transitions_v1.jsonl")


def test_identical_backends_are_perfect_under_small_fixture_policy() -> None:
    policy = BackendComparisonPolicy(min_aligned_actions=1)
    result = compare_backends(FIXTURE, FIXTURE, policy=policy)

    assert result.aligned_actions == 2
    assert result.reference_action_alignment == 1.0
    assert result.candidate_action_alignment == 1.0
    assert result.visible_unit_precision == 1.0
    assert result.visible_unit_recall == 1.0
    assert result.unit_position_mae == 0.0
    assert result.unit_hp_mae == 0.0
    assert result.promotion_eligible


def test_large_position_drift_blocks_promotion(tmp_path: Path) -> None:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    changed = []
    for line in lines:
        payload = json.loads(line)
        for state in ("observation", "next_observation"):
            for unit in payload[state]["units"]:
                if unit["visible"]:
                    unit["x"] += 200
        changed.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))

    candidate = tmp_path / "candidate.jsonl"
    candidate.write_text("\n".join(changed) + "\n", encoding="utf-8")

    policy = BackendComparisonPolicy(min_aligned_actions=1)
    result = compare_backends(FIXTURE, candidate, policy=policy)

    assert result.unit_position_mae > policy.max_unit_position_mae
    assert not result.promotion_eligible
    assert "unit-position MAE above threshold" in result.promotion_failures
