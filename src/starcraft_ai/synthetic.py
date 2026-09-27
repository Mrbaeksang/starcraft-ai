from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from starcraft_ai.models.world_model import WorldModelConfig


@dataclass(frozen=True, slots=True)
class SyntheticBatch:
    entities: Tensor
    next_entities: Tensor
    entity_mask: Tensor
    action_type: Tensor
    action_features: Tensor
    reward: Tensor
    terminal: Tensor


def make_synthetic_batch(
    config: WorldModelConfig,
    *,
    batch_size: int = 32,
    entities_per_state: int = 24,
    device: torch.device,
    seed: int,
) -> SyntheticBatch:
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)

    entities = torch.randn(
        batch_size,
        entities_per_state,
        config.entity_features,
        generator=generator,
        device=device,
    )
    entity_mask = torch.ones(batch_size, entities_per_state, dtype=torch.bool, device=device)
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
    next_entities = entities + 0.05 * action_signal + 0.02 * type_signal

    reward = next_entities[:, :, 0].mean(dim=1) - entities[:, :, 0].mean(dim=1)
    terminal = torch.zeros(batch_size, dtype=entities.dtype, device=device)

    return SyntheticBatch(
        entities=entities,
        next_entities=next_entities,
        entity_mask=entity_mask,
        action_type=action_type,
        action_features=action_features,
        reward=reward,
        terminal=terminal,
    )
