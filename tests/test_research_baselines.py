import math

from starcraft_ai.research_baselines import run_baseline_benchmark


def test_all_baselines_run_and_report_metrics() -> None:
    for model in ("mlp", "recurrent", "jepa"):
        result = run_baseline_benchmark(
            model_name=model,
            steps=2,
            seed=5,
            device_name="cpu",
        )

        assert result.parameters > 0
        assert result.first_loss > 0
        assert result.final_loss > 0
        assert math.isfinite(result.reward_mae)
        assert math.isfinite(result.terminal_brier)
        assert math.isfinite(result.probe_economy_mae)
        assert math.isfinite(result.probe_army_mae)
        assert math.isfinite(result.probe_tech_mae)
        assert math.isfinite(result.probe_map_control_mae)
        assert math.isfinite(result.rollout_h1)
        assert math.isfinite(result.rollout_h5)
        assert math.isfinite(result.rollout_h10)
