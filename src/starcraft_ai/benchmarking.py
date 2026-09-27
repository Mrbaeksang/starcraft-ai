from __future__ import annotations

import math
import time
from dataclasses import dataclass

import torch

from starcraft_ai.models.world_model import LatentWorldModel, WorldModelConfig
from starcraft_ai.synthetic import make_synthetic_batch
from starcraft_ai.training import resolve_device


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    profile: str
    seed: int
    steps: int
    device: str
    parameters: int
    first_loss: float
    final_loss: float
    best_loss: float
    loss_ratio: float
    elapsed_seconds: float
    steps_per_second: float


def config_for_profile(profile: str) -> WorldModelConfig:
    profiles = {
        "tiny": WorldModelConfig(
            entity_features=12,
            action_types=8,
            action_features=4,
            model_dim=32,
            latent_dim=32,
            attention_heads=4,
            transformer_layers=1,
        ),
        "small": WorldModelConfig(
            entity_features=16,
            action_types=12,
            action_features=6,
            model_dim=64,
            latent_dim=64,
            attention_heads=4,
            transformer_layers=2,
        ),
        "medium": WorldModelConfig(
            entity_features=24,
            action_types=16,
            action_features=8,
            model_dim=128,
            latent_dim=128,
            attention_heads=8,
            transformer_layers=4,
        ),
    }
    try:
        return profiles[profile]
    except KeyError as error:
        choices = ", ".join(sorted(profiles))
        raise ValueError(f"unknown profile {profile!r}; expected one of: {choices}") from error


def benchmark_synthetic_dynamics(
    *,
    profile: str,
    steps: int,
    seed: int,
    device_name: str,
) -> BenchmarkResult:
    if steps < 1:
        raise ValueError("steps must be >= 1")

    torch.manual_seed(seed)
    device = resolve_device(device_name)
    config = config_for_profile(profile)

    model = LatentWorldModel(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)

    batch = make_synthetic_batch(
        config,
        batch_size=32,
        entities_per_state=16,
        device=device,
        seed=seed,
    )

    first_loss = math.nan
    final_loss = math.nan
    best_loss = math.inf

    started = time.perf_counter()
    model.train()
    for step in range(steps):
        losses = model.loss(
            entities=batch.entities,
            next_entities=batch.next_entities,
            action_type=batch.action_type,
            action_features=batch.action_features,
            reward=batch.reward,
            terminal=batch.terminal,
            entity_mask=batch.entity_mask,
            next_entity_mask=batch.entity_mask,
        )

        optimizer.zero_grad(set_to_none=True)
        losses["loss"].backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        model.update_target_encoder(momentum=0.99)

        current_loss = float(losses["loss"].detach().cpu())
        if step == 0:
            first_loss = current_loss
        final_loss = current_loss
        best_loss = min(best_loss, current_loss)

    elapsed = time.perf_counter() - started
    parameters = sum(parameter.numel() for parameter in model.parameters())

    if not all(math.isfinite(value) for value in (first_loss, final_loss, best_loss)):
        raise RuntimeError("benchmark produced a non-finite loss")

    return BenchmarkResult(
        profile=profile,
        seed=seed,
        steps=steps,
        device=str(device),
        parameters=parameters,
        first_loss=first_loss,
        final_loss=final_loss,
        best_loss=best_loss,
        loss_ratio=final_loss / first_loss,
        elapsed_seconds=elapsed,
        steps_per_second=steps / max(elapsed, 1e-9),
    )
