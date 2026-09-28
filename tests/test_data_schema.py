import json
from pathlib import Path

import pytest

from starcraft_ai.data import (
    ActionV1,
    TransitionV1,
    UnitObservationV1,
    iter_jsonl_v1,
    sha256_file,
)

FIXTURES = Path("tests/fixtures")


def test_fixture_round_trips_canonically() -> None:
    transitions = list(iter_jsonl_v1(FIXTURES / "transitions_v1.jsonl"))
    assert len(transitions) == 2

    source_lines = [
        line
        for line in (FIXTURES / "transitions_v1.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert [item.canonical_json() for item in transitions] == source_lines


def test_fixture_manifest_hash_matches() -> None:
    manifest = json.loads((FIXTURES / "transitions_v1.manifest.json").read_text(encoding="utf-8"))
    payload = FIXTURES / manifest["files"][0]["path"]

    assert payload.stat().st_size == manifest["files"][0]["bytes"]
    assert sha256_file(payload) == manifest["files"][0]["sha256"]
    assert sum(1 for _ in iter_jsonl_v1(payload)) == manifest["transition_count"]


def test_unknown_future_fields_are_rejected() -> None:
    transition = next(iter_jsonl_v1(FIXTURES / "transitions_v1.jsonl"))
    payload = transition.to_dict()
    payload["future_enemy_position"] = [999, 999]

    with pytest.raises(ValueError, match="unknown fields"):
        TransitionV1.from_dict(payload)


def test_hidden_enemy_cannot_claim_current_position() -> None:
    with pytest.raises(ValueError, match="last-seen"):
        UnitObservationV1(
            unit_id=4,
            type_id=65,
            owner="enemy",
            x=10,
            y=20,
            hp=40,
            hp_max=80,
            shields=0,
            energy=0,
            order_id=0,
            visible=False,
            position_source="current",
            last_seen_frame=None,
        )


def test_invalid_action_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires a target position"):
        ActionV1(
            frame=10,
            player_id=0,
            action_type="ATTACK_MOVE",
            actor_unit_ids=(1,),
            target_unit_id=None,
            target_x=None,
            target_y=None,
            argument_type_id=None,
        )
