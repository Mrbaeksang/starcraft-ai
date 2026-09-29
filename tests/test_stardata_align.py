import json
from pathlib import Path

from starcraft_ai.data.stardata_align import align_stardata_actions


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_actions_align_to_surrounding_sampled_states(tmp_path: Path) -> None:
    states = tmp_path / "states.jsonl"
    actions = tmp_path / "actions.jsonl"
    output = tmp_path / "aligned.jsonl"

    _write_jsonl(
        states,
        [
            {"sample_index": 0, "approx_game_frame": 0, "units": [{"unit_id": 7, "player_id": 0}]},
            {"sample_index": 1, "approx_game_frame": 3, "units": [{"unit_id": 8, "player_id": 1}]},
            {"sample_index": 2, "approx_game_frame": 6, "units": [{"unit_id": 9, "player_id": 1}]},
            {"sample_index": 3, "approx_game_frame": 9, "units": []},
        ],
    )
    _write_jsonl(
        actions,
        [
            {"ordinal": 0, "frame": 1, "player_id": 0, "selected_unit_tags": [7], "command": {}},
            {"ordinal": 1, "frame": 3, "player_id": 0, "selected_unit_tags": [8], "command": {}},
            {"ordinal": 2, "frame": 8, "player_id": 1, "selected_unit_tags": [9], "command": {}},
        ],
    )

    result = align_stardata_actions(states, actions, output)
    rows = [json.loads(line) for line in output.read_text().splitlines()]

    assert result.aligned_actions == 3
    assert result.max_before_gap == 2
    assert result.max_after_gap == 3
    assert result.selected_actor_refs == 3
    assert result.raw_actor_id_matches == 3
    assert result.raw_actor_owner_matches == 2
    assert rows[0]["state_sample_index"] == 0
    assert rows[0]["next_state_sample_index"] == 1
    assert rows[1]["state_sample_index"] == 1
    assert rows[1]["next_state_sample_index"] == 2
    assert rows[2]["state_sample_index"] == 2
    assert rows[2]["next_state_sample_index"] == 3


def test_reports_cross_source_actor_id_mismatch(tmp_path: Path) -> None:
    states = tmp_path / "states.jsonl"
    actions = tmp_path / "actions.jsonl"
    output = tmp_path / "aligned.jsonl"

    _write_jsonl(
        states,
        [
            {"sample_index": 0, "approx_game_frame": 0, "units": [{"unit_id": 2, "player_id": 0}]},
            {"sample_index": 1, "approx_game_frame": 3, "units": []},
        ],
    )
    _write_jsonl(
        actions,
        [{"ordinal": 0, "frame": 1, "player_id": 0, "selected_unit_tags": [3585]}],
    )

    result = align_stardata_actions(states, actions, output)

    assert result.aligned_actions == 1
    assert result.selected_actor_refs == 1
    assert result.raw_actor_id_matches == 0
    assert result.raw_actor_owner_matches == 0
