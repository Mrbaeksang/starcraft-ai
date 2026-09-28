from pathlib import Path

import pytest

from starcraft_ai.transition_training import train_transition_dataset

FIXTURE = Path("tests/fixtures/transitions_v1.jsonl")


@pytest.mark.parametrize("model", ["mlp", "recurrent", "jepa"])
def test_transition_training_smoke(model: str) -> None:
    result = train_transition_dataset(
        [FIXTURE],
        model_name=model,
        steps=2,
        batch_size=2,
        seed=11,
        device_name="cpu",
        allow_single_episode_smoke=True,
    )

    assert result.transitions == 2
    assert result.episodes == 1
    assert result.smoke_only
    assert result.parameters > 0
    assert result.first_loss > 0
    assert result.final_loss > 0
    assert result.eval_loss > 0


def test_single_episode_is_rejected_for_claimable_experiment() -> None:
    with pytest.raises(ValueError, match="held-out episode-level"):
        train_transition_dataset(
            [FIXTURE],
            model_name="jepa",
            steps=1,
            batch_size=2,
            seed=7,
            device_name="cpu",
        )
