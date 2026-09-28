from __future__ import annotations

from dataclasses import asdict, dataclass

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from starcraft_ai.evaluation import (
    linear_probe_mae,
    reward_mae,
    synthetic_probe_targets,
    terminal_brier,
)
from starcraft_ai.models.baselines import DirectDynamicsMLP, RecurrentDynamicsBaseline, masked_mean
from starcraft_ai.models.world_model import LatentWorldModel, WorldModelConfig
from starcraft_ai.synthetic import SyntheticBatch, make_synthetic_batch
from starcraft_ai.training import resolve_device


@dataclass(frozen=True, slots=True)
class BaselineBenchmarkResult:
    model: str
    seed: int
    steps: int
    parameters: int
    first_loss: float
    final_loss: float
    reward_mae: float
    terminal_brier: float
    probe_economy_mae: float
    probe_army_mae: float
    probe_tech_mae: float
    probe_map_control_mae: float
    rollout_h1: float
    rollout_h5: float
    rollout_h10: float

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


def baseline_config() -> WorldModelConfig:
    return WorldModelConfig(
        entity_features=12,
        action_types=8,
        action_features=4,
        model_dim=64,
        latent_dim=64,
        attention_heads=4,
        transformer_layers=2,
    )


def _with_terminal_labels(batch: SyntheticBatch) -> SyntheticBatch:
    terminal = (
        batch.next_entities[:, :, 0].mean(dim=1) > 0.05
    ).to(batch.entities.dtype)
    return SyntheticBatch(
        entities=batch.entities,
        next_entities=batch.next_entities,
        entity_mask=batch.entity_mask,
        action_type=batch.action_type,
        action_features=batch.action_features,
        reward=batch.reward,
        terminal=terminal,
    )


def _make_model(name: str, config: WorldModelConfig) -> nn.Module:
    if name == "mlp":
        return DirectDynamicsMLP(config)
    if name == "recurrent":
        return RecurrentDynamicsBaseline(config)
    if name == "jepa":
        return LatentWorldModel(config)
    raise ValueError("model must be one of: mlp, recurrent, jepa")


def _loss(model: nn.Module, batch: SyntheticBatch) -> dict[str, Tensor]:
    return model.loss(
        entities=batch.entities,
        next_entities=batch.next_entities,
        action_type=batch.action_type,
        action_features=batch.action_features,
        reward=batch.reward,
        terminal=batch.terminal,
        entity_mask=batch.entity_mask,
        next_entity_mask=batch.entity_mask,
    )


def _representation(model: nn.Module, name: str, batch: SyntheticBatch) -> Tensor:
    if name == "jepa":
        return model.encode(batch.entities, batch.entity_mask)
    return model.encode(batch.entities, batch.entity_mask)


def _prediction_heads(
    model: nn.Module,
    name: str,
    batch: SyntheticBatch,
) -> tuple[Tensor, Tensor]:
    prediction = model.predict(
        batch.entities,
        batch.action_type,
        batch.action_features,
        batch.entity_mask,
    )
    if name == "jepa":
        return prediction["reward"], prediction["terminal_logit"]
    return prediction.reward, prediction.terminal_logit


@torch.no_grad()
def _rollout_errors(
    model: nn.Module,
    name: str,
    config: WorldModelConfig,
    *,
    seed: int,
    device: torch.device,
) -> dict[int, float]:
    batch_size = 32
    entities_per_state = 16
    generator = torch.Generator(device=device)
    generator.manual_seed(seed + 30_000)

    entities = torch.randn(
        batch_size,
        entities_per_state,
        config.entity_features,
        generator=generator,
        device=device,
    )
    mask = torch.ones(
        batch_size,
        entities_per_state,
        dtype=torch.bool,
        device=device,
    )

    if name == "mlp":
        predicted_features = masked_mean(entities, mask)
    elif name == "recurrent":
        hidden = model.encode(entities, mask)
    else:
        latent = model.encode(entities, mask)

    errors: dict[int, float] = {}
    for horizon in range(1, 11):
        action_type = torch.randint(
            0,
            config.action_types,
            (batch_size,),
            generator=generator,
            device=device,
        )
        action_features = torch.randn(
            batch_size,
            config.action_features,
            generator=generator,
            device=device,
        )

        action_signal = action_features.mean(dim=-1, keepdim=True).unsqueeze(-1)
        type_signal = action_type.to(entities.dtype).view(batch_size, 1, 1)
        type_signal = (type_signal / max(config.action_types - 1, 1)) - 0.5
        entities = entities + 0.05 * action_signal + 0.02 * type_signal
        true_features = masked_mean(entities, mask)

        if name == "mlp":
            predicted_features, _ = model.step_features(
                predicted_features,
                action_type,
                action_features,
            )
            error = F.mse_loss(predicted_features, true_features)
        elif name == "recurrent":
            predicted_features, hidden = model.step_hidden(
                hidden,
                action_type,
                action_features,
            )
            error = F.mse_loss(predicted_features, true_features)
        else:
            latent = model.predict_from_latent(
                latent,
                action_type,
                action_features,
            )
            target_latent = model.encode_target(entities, mask)
            error = (1.0 - F.cosine_similarity(latent, target_latent)).mean()

        if horizon in {1, 5, 10}:
            errors[horizon] = float(error.detach().cpu())

    return errors


def run_baseline_benchmark(
    *,
    model_name: str,
    steps: int,
    seed: int,
    device_name: str,
) -> BaselineBenchmarkResult:
    if steps < 1:
        raise ValueError("steps must be >= 1")

    device = resolve_device(device_name)
    torch.manual_seed(seed)
    config = baseline_config()
    model = _make_model(model_name, config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)

    train_batch = _with_terminal_labels(
        make_synthetic_batch(
            config,
            batch_size=96,
            entities_per_state=16,
            device=device,
            seed=seed,
        )
    )

    first_loss = 0.0
    final_loss = 0.0
    model.train()
    for step in range(steps):
        losses = _loss(model, train_batch)
        optimizer.zero_grad(set_to_none=True)
        losses["loss"].backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        if model_name == "jepa":
            model.update_target_encoder(momentum=0.99)

        value = float(losses["loss"].detach().cpu())
        if step == 0:
            first_loss = value
        final_loss = value

    eval_batch = _with_terminal_labels(
        make_synthetic_batch(
            config,
            batch_size=128,
            entities_per_state=16,
            device=device,
            seed=seed + 10_000,
        )
    )

    model.eval()
    with torch.no_grad():
        representation = _representation(model, model_name, eval_batch)
        predicted_reward, terminal_logit = _prediction_heads(
            model,
            model_name,
            eval_batch,
        )
        probes = linear_probe_mae(
            representation,
            synthetic_probe_targets(eval_batch.entities),
        )
        rollout = _rollout_errors(
            model,
            model_name,
            config,
            seed=seed,
            device=device,
        )

    return BaselineBenchmarkResult(
        model=model_name,
        seed=seed,
        steps=steps,
        parameters=sum(parameter.numel() for parameter in model.parameters()),
        first_loss=first_loss,
        final_loss=final_loss,
        reward_mae=reward_mae(predicted_reward, eval_batch.reward),
        terminal_brier=terminal_brier(terminal_logit, eval_batch.terminal),
        probe_economy_mae=probes.economy_mae,
        probe_army_mae=probes.army_mae,
        probe_tech_mae=probes.tech_mae,
        probe_map_control_mae=probes.map_control_mae,
        rollout_h1=rollout[1],
        rollout_h5=rollout[5],
        rollout_h10=rollout[10],
    )
