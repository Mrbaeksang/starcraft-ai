import torch

from starcraft_ai.planning import (
    BrokenSequenceScorer,
    cem_plan,
    random_shooting,
    receding_horizon_action,
)


class ToyScorer:
    action_types = 3
    action_features = 2

    def score(
        self,
        initial_state,
        action_type_sequence,
        action_feature_sequence,
        *,
        discount,
        uncertainty_penalty,
    ):
        del initial_state, uncertainty_penalty
        weights = torch.tensor(
            [discount**step for step in range(action_type_sequence.shape[1])],
            device=action_type_sequence.device,
        )
        discrete = (action_type_sequence == 2).float()
        continuous = 1.0 - (action_feature_sequence[..., 0] - 0.75).abs()
        return ((discrete + continuous) * weights).sum(dim=1)


def test_random_shooting_returns_first_receding_horizon_action() -> None:
    state = torch.zeros(8)
    result = random_shooting(
        ToyScorer(),
        state,
        horizon=3,
        population=512,
        seed=3,
        uncertainty_penalty=0.0,
    )

    action_type, action_features = receding_horizon_action(result)
    assert 0 <= action_type < 3
    assert action_features.shape == (2,)
    assert result.sequence_action_types.shape == (3,)
    assert result.sequence_action_features.shape == (3, 2)


def test_cem_outperforms_broken_control_on_toy_objective() -> None:
    state = torch.zeros(8)
    good = cem_plan(
        ToyScorer(),
        state,
        horizon=3,
        population=256,
        iterations=4,
        seed=9,
        uncertainty_penalty=0.0,
    )
    broken = cem_plan(
        BrokenSequenceScorer(action_types=3, action_features=2),
        state,
        horizon=3,
        population=256,
        iterations=4,
        seed=9,
        uncertainty_penalty=0.0,
    )

    assert good.score.item() > 3.0
    assert broken.score.item() == 0.0
