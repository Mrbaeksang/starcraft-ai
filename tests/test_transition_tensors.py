from pathlib import Path

from starcraft_ai.data import iter_jsonl_v1
from starcraft_ai.data.tensors import (
    ACTION_FEATURES,
    ENTITY_FEATURES,
    transitions_to_tensors,
)


def test_transition_fixture_becomes_model_tensors() -> None:
    transitions = list(iter_jsonl_v1(Path("tests/fixtures/transitions_v1.jsonl")))
    batch = transitions_to_tensors(transitions)

    assert batch.entities.shape[0] == 2
    assert batch.entities.shape[-1] == ENTITY_FEATURES
    assert batch.action_features.shape == (2, ACTION_FEATURES)
    assert batch.entity_mask[:, 0].all()
    assert batch.next_entity_mask[:, 0].all()
    assert batch.action_type.dtype.is_floating_point is False
