from __future__ import annotations

from dataclasses import dataclass

import torch

from starcraft_ai.models.world_model import LatentWorldModel, WorldModelConfig
from starcraft_ai.synthetic import make_synthetic_batch


@dataclass(frozen=True, slots=True)
class SmokeTrainResult:
    first_loss: float
    final_loss: float
    device: str


def resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    return torch.device(requested)


def smoke_train(*, steps: int, device_name: str, seed: int = 7) -> SmokeTrainResult:
    if steps < 1:
        raise ValueError("steps must be >= 1")

    torch.manual_seed(seed)
    device = resolve_device(device_name)

    config = WorldModelConfig(
        entity_features=12,
        action_types=8,
        action_features=4,
        model_dim=64,
        latent_dim=64,
        attention_heads=4,
        transformer_layers=2,
    )
    model = LatentWorldModel(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)

    first_loss = 0.0
    final_loss = 0.0
    model.train()

    for step in range(steps):
        batch = make_synthetic_batch(
            config,
            batch_size=32,
            entities_per_state=16,
            device=device,
            seed=seed + step,
        )
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

    return SmokeTrainResult(first_loss=first_loss, final_loss=final_loss, device=str(device))
