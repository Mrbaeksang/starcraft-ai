import math

from starcraft_ai.benchmarking import benchmark_synthetic_dynamics, config_for_profile


def test_profile_is_available() -> None:
    config = config_for_profile("tiny")
    assert config.model_dim == 32


def test_synthetic_benchmark_is_finite() -> None:
    result = benchmark_synthetic_dynamics(
        profile="tiny",
        steps=2,
        seed=17,
        device_name="cpu",
    )

    assert result.parameters > 0
    assert result.steps_per_second > 0
    assert math.isfinite(result.first_loss)
    assert math.isfinite(result.final_loss)
    assert math.isfinite(result.loss_ratio)
