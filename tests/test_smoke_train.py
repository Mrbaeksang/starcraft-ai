from starcraft_ai.training import smoke_train


def test_smoke_train_runs_on_cpu() -> None:
    result = smoke_train(steps=2, device_name="cpu", seed=11)

    assert result.device == "cpu"
    assert result.first_loss > 0
    assert result.final_loss > 0
